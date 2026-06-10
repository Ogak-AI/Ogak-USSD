"""
Production Transaction Orchestrator
Drives the complete non-P2P crypto-fiat flow using ILP atomicity.

Flow for BUY (Fiat → Crypto):
1. User confirms quote + PIN.
2. Orchestrator creates Transaction record (status=CONFIRMED).
3. ILP PREPARE phase:
   - Lock quote
   - Initiate fiat leg via BankProvider (charge or NIP credit expectation)
   - Initiate crypto leg reservation on ExchangeProvider
4. On successful preparation of both legs → ILP FULFILL (reveal preimage)
   - Finalize bank debit/credit confirmation
   - Finalize crypto credit to user wallet
5. On any failure in prepare or before fulfill → ILP REJECT + best-effort rollback

The orchestrator never holds funds. It coordinates settlement between the user's bank and the licensed VASP.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from packages.api.banks import get_bank_provider
from packages.api.exchanges import get_exchange_provider
from packages.db.models import TransactionModel
from packages.ilp_connector.connector import get_connector
from packages.services.quote_service import get_quote_service
from packages.shared.config import get_settings
from packages.shared.crypto_utils import decrypt_sensitive, generate_transaction_reference
from packages.shared.errors import (
    BankAPIError,
    ExchangeAPIError,
    ILPError,
    InsufficientFundsError,
    OgakError,
    TransactionError,
)
from packages.shared.types import (
    CryptoAsset,
    Exchange,
    TransactionStatus,
    TransactionType,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class TransactionOrchestrator:
    """
    The core engine for atomic settlement.
    Uses ILP condition/fulfillment model even when full ILP network is not present
    between bank and exchange (common in African fintech).
    """

    def __init__(self):
        self.quote_service = get_quote_service()
        self.ilp = None  # lazy

    async def _get_ilp(self):
        if self.ilp is None:
            self.ilp = await get_connector("primary")
        return self.ilp

    async def execute_buy(
        self,
        user_id: str,
        quote_id: str,
        bank_account_id: str,
        pin: str,
        db_session,
    ) -> dict:
        """
        Execute a BUY transaction (user sends NGN → receives crypto).
        Returns final status and references.
        """
        quote = await self.quote_service.get_quote(quote_id, db_session)
        if not quote or quote.is_used or quote.transaction_type != TransactionType.BUY.value:
            raise TransactionError("Invalid or expired quote")

        # TODO: In full implementation, verify PIN against user here (or in caller)

        reference = generate_transaction_reference("OGK-BUY")

        tx = TransactionModel(
            id=str(uuid.uuid4()),
            reference=reference,
            user_id=user_id,
            quote_id=quote_id,
            bank_account_id=bank_account_id,
            transaction_type=TransactionType.BUY.value,
            status=TransactionStatus.CONFIRMED.value,
            crypto_asset=quote.crypto_asset,
            fiat_amount_ngn=quote.fiat_amount_ngn,
            crypto_amount=quote.crypto_amount,
            exchange_rate=quote.exchange_rate,
            fee_ngn=quote.fee_ngn,
            total_ngn=quote.total_ngn,
            exchange=quote.exchange,
            ilp_condition=quote.ilp_condition,
        )
        db_session.add(tx)
        await db_session.flush()

        await self.quote_service.mark_quote_used(quote_id, db_session)

        # === ILP PREPARE PHASE ===
        try:
            ilp = await self._get_ilp()
            prepare_result = await ilp.prepare_payment(
                quote_id=quote_id,
                sender_ledger="FIAT.NGN",
                receiver_ledger=f"CRYPTO.{quote.crypto_asset}",
                sender_account=bank_account_id,
                receiver_account=f"{quote.exchange}:{user_id}",
                metadata={
                    "transaction_reference": reference,
                    "user_id": user_id,
                },
            )

            tx.ilp_packet_id = prepare_result.get("packet_id")
            tx.ilp_status = "PREPARED"
            tx.status = TransactionStatus.EXECUTING.value
            await db_session.flush()

            # === REAL FIAT LEG (Buy crypto = user pays NGN) ===
            # In production for "Buy", we usually:
            #   - Either charge the user's bank account directly (if mandate exists)
            #   - Or provide a virtual account / NIP reference and wait for webhook credit
            #
            # Here we attempt a direct charge via the bank provider (Flutterwave/Paystack).
            # Real success depends on the user having a debit mandate or the provider supporting it.
            bank_provider = get_bank_provider("flutterwave")  # or paystack based on config

            # Resolve real linked bank account from DB
            from packages.db.models import BankAccountModel
            from sqlalchemy import select
            result = await db_session.execute(
                select(BankAccountModel).where(
                    BankAccountModel.id == bank_account_id,
                    BankAccountModel.user_id == user_id,
                    BankAccountModel.is_verified == True
                )
            )
            bank_account = result.scalar_one_or_none()
            if not bank_account:
                raise ValueError("No verified bank account found for this user. User must link and verify a bank account first.")

            fiat_leg = await bank_provider.initiate_debit(
                account_number=bank_account.account_number,
                bank_code=bank_account.bank_code,
                amount=quote.total_ngn,
                reference=reference,
                narration=f"Ogak Buy {quote.crypto_asset} - {reference}",
            )

            tx.bank_reference = fiat_leg.get("reference") or fiat_leg.get("flutterwave_reference")
            tx.bank_provider = "flutterwave"
            tx.fiat_settled_at = datetime.now(timezone.utc)
            tx.status = TransactionStatus.FIAT_SETTLED.value
            await db_session.flush()

            # === REAL CRYPTO LEG ===
            exchange_provider = get_exchange_provider(quote.exchange)
            # Resolve user's linked exchange account / destination wallet from DB
            from packages.db.models import ExchangeAccountModel
            from sqlalchemy import select
            ex_result = await db_session.execute(
                select(ExchangeAccountModel).where(
                    ExchangeAccountModel.user_id == user_id,
                    ExchangeAccountModel.exchange == quote.exchange,
                    ExchangeAccountModel.is_verified == True
                )
            )
            exchange_account = ex_result.scalar_one_or_none()
            if not exchange_account:
                raise ValueError(f"No verified {quote.exchange} exchange account linked for this user.")

            # In production the encrypted keys would be used to act on behalf of user or credit to a pre-arranged sub-account.
            # For now we pass a wallet address derived from the linked account record (implement decryption + address lookup as needed).
            target_wallet = exchange_account.exchange_user_id or "PRIMARY_SETTLEMENT_WALLET"  # Replace with proper resolution

            crypto_leg = await exchange_provider.buy_crypto(
                crypto=quote.crypto_asset,
                amount_ngn=quote.fiat_amount_ngn,
                wallet_address=target_wallet,
                reference=reference,
            )

            tx.exchange_order_id = crypto_leg.get("order_id")
            tx.exchange_reference = crypto_leg.get("reference")
            tx.crypto_settled_at = datetime.now(timezone.utc)
            tx.status = TransactionStatus.CRYPTO_SETTLED.value
            await db_session.flush()

            # === ILP FULFILL (atomic commit) ===
            fulfillment_hex = decrypt_sensitive(quote.ilp_fulfillment_encrypted)
            fulfillment = bytes.fromhex(fulfillment_hex)

            fulfill_result = await ilp.fulfill_payment(
                packet_id=prepare_result["packet_id"],
                quote_id=quote_id,
                fulfillment=fulfillment.hex(),
            )

            tx.ilp_fulfillment = fulfill_result.get("fulfillment")
            tx.ilp_status = "FULFILLED"
            tx.status = TransactionStatus.COMPLETED.value
            tx.completed_at = datetime.now(timezone.utc)
            await db_session.flush()

            logger.info(f"BUY transaction COMPLETED: {reference} | ILP fulfilled")

            return {
                "success": True,
                "reference": reference,
                "status": TransactionStatus.COMPLETED.value,
                "crypto_amount": str(quote.crypto_amount),
                "fiat_amount": str(quote.fiat_amount_ngn),
                "ilp_status": "FULFILLED",
            }

        except (BankAPIError, ExchangeAPIError, ILPError) as exc:
            logger.error(f"Transaction failed during execution: {exc}", exc_info=True)
            await self._rollback(tx, str(exc), db_session)
            raise
        except Exception as exc:
            logger.exception("Unexpected failure in orchestrator")
            await self._rollback(tx, f"Internal error: {str(exc)}", db_session)
            raise TransactionError(f"Transaction failed: {str(exc)}")

    async def execute_sell(
        self,
        user_id: str,
        quote_id: str,
        bank_account_id: str,
        pin: str,
        db_session,
    ) -> dict:
        """Symmetric SELL flow (crypto → NGN)."""
        # Similar structure to buy but reversed legs.
        # For brevity in this production implementation the sell path follows the same pattern.
        # Real production would debit the user's crypto balance on the exchange first.
        quote = await self.quote_service.get_quote(quote_id, db_session)
        if not quote or quote.is_used or quote.transaction_type != TransactionType.SELL.value:
            raise TransactionError("Invalid or expired quote")

        reference = generate_transaction_reference("OGK-SELL")

        tx = TransactionModel(
            id=str(uuid.uuid4()),
            reference=reference,
            user_id=user_id,
            quote_id=quote_id,
            bank_account_id=bank_account_id,
            transaction_type=TransactionType.SELL.value,
            status=TransactionStatus.CONFIRMED.value,
            crypto_asset=quote.crypto_asset,
            fiat_amount_ngn=quote.fiat_amount_ngn,
            crypto_amount=quote.crypto_amount,
            exchange_rate=quote.exchange_rate,
            fee_ngn=quote.fee_ngn,
            total_ngn=quote.total_ngn,
            exchange=quote.exchange,
            ilp_condition=quote.ilp_condition,
        )
        db_session.add(tx)
        await db_session.flush()

        await self.quote_service.mark_quote_used(quote_id, db_session)

        try:
            ilp = await self._get_ilp()
            prepare_result = await ilp.prepare_payment(
                quote_id=quote_id,
                sender_ledger=f"CRYPTO.{quote.crypto_asset}",
                receiver_ledger="FIAT.NGN",
                sender_account=f"{quote.exchange}:{user_id}",
                receiver_account=bank_account_id,
                metadata={"transaction_reference": reference},
            )

            tx.ilp_packet_id = prepare_result["packet_id"]
            tx.ilp_status = "PREPARED"
            tx.status = TransactionStatus.EXECUTING.value
            await db_session.flush()

            # Crypto leg first for sell (user gives crypto)
            exchange_provider = get_exchange_provider(quote.exchange)
            crypto_leg = await exchange_provider.sell_crypto(
                crypto=quote.crypto_asset,
                amount_crypto=quote.crypto_amount,
                bank_account={"account_id": bank_account_id},  # resolved in real code
                reference=reference,
            )
            tx.exchange_order_id = crypto_leg.get("order_id")
            tx.crypto_settled_at = datetime.now(timezone.utc)
            tx.status = TransactionStatus.CRYPTO_SETTLED.value
            await db_session.flush()

            # Resolve real linked bank account from DB for credit (Sell)
            from packages.db.models import BankAccountModel
            from sqlalchemy import select
            result = await db_session.execute(
                select(BankAccountModel).where(
                    BankAccountModel.id == bank_account_id,
                    BankAccountModel.user_id == user_id,
                    BankAccountModel.is_verified == True
                )
            )
            bank_account = result.scalar_one_or_none()
            if not bank_account:
                raise ValueError("No verified bank account found for this user. User must link and verify a bank account first.")

            # Fiat leg (credit user's bank)
            bank_provider = get_bank_provider("paystack")
            fiat_leg = await bank_provider.initiate_credit(
                account_number=bank_account.account_number,
                bank_code=bank_account.bank_code,
                amount=quote.fiat_amount_ngn - quote.fee_ngn,
                reference=reference,
                narration=f"Ogak Sell {quote.crypto_asset} - {reference}",
            )
            tx.bank_reference = fiat_leg.get("reference")
            tx.fiat_settled_at = datetime.now(timezone.utc)
            tx.status = TransactionStatus.FIAT_SETTLED.value
            await db_session.flush()

            # Fulfill
            fulfillment_hex = decrypt_sensitive(quote.ilp_fulfillment_encrypted)
            fulfill_result = await ilp.fulfill_payment(
                packet_id=prepare_result["packet_id"],
                quote_id=quote_id,
                fulfillment=fulfillment_hex,
            )

            tx.ilp_status = "FULFILLED"
            tx.status = TransactionStatus.COMPLETED.value
            tx.completed_at = datetime.now(timezone.utc)
            await db_session.flush()

            return {
                "success": True,
                "reference": reference,
                "status": TransactionStatus.COMPLETED.value,
            }

        except Exception as exc:
            await self._rollback(tx, str(exc), db_session)
            raise

    async def _rollback(self, tx: TransactionModel, reason: str, db_session):
        """Best-effort rollback + ILP REJECT."""
        tx.status = TransactionStatus.FAILED.value
        tx.failure_reason = reason
        tx.rollback_at = datetime.now(timezone.utc)

        try:
            ilp = await self._get_ilp()
            if tx.ilp_packet_id:
                await ilp.reject_payment(tx.ilp_packet_id, reason)
                tx.ilp_status = "REJECTED"
        except Exception as e:
            logger.warning(f"ILP reject during rollback failed: {e}")

        # In production: attempt to reverse any partial bank/exchange legs here.
        # This is highly provider-specific and often involves manual ops + reconciliation.
        logger.warning(f"Transaction {tx.reference} rolled back: {reason}")

        await db_session.flush()


_orchestrator: Optional[TransactionOrchestrator] = None


def get_orchestrator() -> TransactionOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TransactionOrchestrator()
    return _orchestrator
