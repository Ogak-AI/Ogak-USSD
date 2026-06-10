"""
Production User Service
Handles user lifecycle, PIN verification, KYC tier, daily limits, and account linking.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from packages.db.models import UserModel, BankAccountModel
from packages.shared.constants import NIGERIAN_BANKS
from packages.shared.crypto_utils import hash_pin, verify_pin, sanitize_phone, encrypt_sensitive
from packages.shared.errors import BVNValidationError, ExternalServiceError
from packages.shared.types import KYCTier, Language

import hashlib
import uuid
from packages.api.banks import get_bank_provider

logger = logging.getLogger(__name__)


class UserService:
    async def get_or_create_user(self, phone_number: str, db_session) -> UserModel:
        """Idempotent user lookup/creation by phone. New users start at TIER_0."""
        from sqlalchemy import select

        phone = sanitize_phone(phone_number)
        result = await db_session.execute(
            select(UserModel).where(UserModel.phone_number == phone)
        )
        user = result.scalar_one_or_none()

        if user:
            return user

        # Create new user (they will set PIN on first interaction)
        user = UserModel(
            id=str(uuid.uuid4()),
            phone_number=phone,
            hashed_pin="",  # Must be set during first registration
            pin_salt="",
            language=Language.EN.value,
            kyc_tier=KYCTier.TIER_0.value,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        logger.info(f"New user created: {phone}")
        return user

    async def set_or_verify_pin(
        self, user: UserModel, pin: str, db_session, is_registration: bool = False
    ) -> bool:
        """Set PIN on registration or verify existing PIN."""
        if is_registration or not user.hashed_pin:
            hashed, salt = hash_pin(pin)
            user.hashed_pin = hashed
            user.pin_salt = salt
            user.kyc_tier = max(user.kyc_tier, KYCTier.TIER_1.value)
            await db_session.flush()
            return True

        if verify_pin(pin, user.hashed_pin, user.pin_salt):
            user.pin_attempts = 0
            user.locked_until = None
            await db_session.flush()
            return True

        # Failed attempt
        user.pin_attempts = (user.pin_attempts or 0) + 1
        if user.pin_attempts >= 3:  # from settings in real code
            from datetime import timedelta
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        await db_session.flush()
        return False

    async def is_pin_locked(self, user: UserModel) -> bool:
        if not user.locked_until:
            return False
        return user.locked_until > datetime.now(timezone.utc)

    async def get_user_by_phone(self, phone_number: str, db_session) -> Optional[UserModel]:
        from sqlalchemy import select
        phone = sanitize_phone(phone_number)
        result = await db_session.execute(select(UserModel).where(UserModel.phone_number == phone))
        return result.scalar_one_or_none()

    async def link_bank_account(
        self,
        user: UserModel,
        bank_code: str,
        account_number: str,
        bvn: str,
        db_session,
    ) -> dict:
        """
        Full production bank + BVN linking for TIER_2 upgrade.
        Verifies account name, validates with BVN via provider,
        stores encrypted BVN on user, creates verified BankAccount,
        upgrades kyc_tier to TIER_2.
        """
        if len(bvn) != 11 or not bvn.isdigit():
            raise BVNValidationError("BVN must be 11 digits")

        bank_info = NIGERIAN_BANKS.get(bank_code, {"name": "Unknown Bank"})
        bank_name = bank_info["name"]

        provider = get_bank_provider("flutterwave")  # Primary for verification; change via config if needed

        try:
            # Resolve account to confirm ownership/name
            account_name = await provider.get_account_name(account_number, bank_code)

            # Full verification including BVN (provider will use bvn if supported in its impl)
            verify_result = await provider.verify_account(
                account_number=account_number,
                bank_code=bank_code,
                bvn=bvn,
            )

            if not verify_result.get("verified", False):
                raise BVNValidationError("Account or BVN verification failed. Name may not match.")

            # Prevent duplicate bank accounts
            from sqlalchemy import select
            existing = await db_session.execute(
                select(BankAccountModel).where(
                    BankAccountModel.user_id == user.id,
                    BankAccountModel.bank_code == bank_code,
                    BankAccountModel.account_number == account_number,
                )
            )
            if existing.scalar_one_or_none():
                # Already linked, just ensure tier
                user.kyc_tier = max(user.kyc_tier, KYCTier.TIER_2.value)
                await db_session.flush()
                return {"success": True, "account_name": account_name, "already_linked": True}

            # Encrypt and hash BVN (never store plaintext)
            bvn_encrypted = encrypt_sensitive(bvn)
            bvn_hash = hashlib.sha256(bvn.encode("utf-8")).hexdigest()

            # Create verified bank account record
            is_primary = True
            # Check if user has any primary already
            primary_check = await db_session.execute(
                select(BankAccountModel).where(
                    BankAccountModel.user_id == user.id,
                    BankAccountModel.is_primary == True,
                )
            )
            if primary_check.scalar_one_or_none():
                is_primary = False

            bank_account = BankAccountModel(
                id=str(uuid.uuid4()),
                user_id=user.id,
                bank_code=bank_code,
                bank_name=bank_name,
                account_number=account_number,
                account_name=account_name,
                is_verified=True,
                is_primary=is_primary,
            )
            db_session.add(bank_account)

            # Update user KYC and BVN data
            user.bvn_encrypted = bvn_encrypted
            user.bvn_hash = bvn_hash
            user.kyc_tier = max(user.kyc_tier, KYCTier.TIER_2.value)
            if not user.full_name:
                user.full_name = account_name

            await db_session.flush()

            logger.info(f"Bank + BVN linked for user {user.phone_number} -> Tier 2")

            # Return id so menu can set context for immediate buy/sell use
            return {
                "success": True,
                "account_name": account_name,
                "bank_name": bank_name,
                "new_tier": user.kyc_tier,
                "bank_account_id": bank_account.id,
            }

        except ExternalServiceError as e:
            logger.error(f"Bank verification failed: {e}")
            raise BVNValidationError(f"Verification failed: {str(e)[:100]}")
        except Exception as e:
            logger.error(f"Unexpected error in bank linking: {e}")
            raise BVNValidationError("Could not complete verification. Please try again.")


_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
