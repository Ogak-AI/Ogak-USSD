"""
Production Quote Service
Generates cryptographically-backed ILP quotes with live rates and stores them in DB.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from packages.db.models import QuoteModel
from packages.ilp_connector.connector import get_connector
from packages.services.rate_service import get_rate_service
from packages.shared.config import get_settings
from packages.shared.crypto_utils import generate_ilp_condition, encrypt_sensitive, generate_transaction_reference
from packages.shared.errors import QuoteExpiredError, TransactionLimitError
from packages.shared.types import CryptoAsset, Exchange, KYCTier, QuoteResponse, TransactionType

logger = logging.getLogger(__name__)
settings = get_settings()


class QuoteService:
    """
    Creates and validates quotes using live rates + ILP condition/fulfillment.
    """

    def __init__(self):
        self.rate_service = get_rate_service()
        self.quote_expiry_seconds = settings.rate_quote_expiry_seconds
        self.default_spread = settings.rate_spread_bps

    async def create_quote(
        self,
        user_id: str,
        transaction_type: TransactionType,
        crypto_asset: CryptoAsset,
        fiat_amount: Optional[Decimal],
        crypto_amount: Optional[Decimal],
        exchange: Exchange,
        user_kyc_tier: KYCTier,
        db_session,
    ) -> QuoteResponse:
        """
        Generate a real quote:
        1. Fetch live rate from exchange.
        2. Apply spread + Ogak fee.
        3. Generate ILP condition + encrypted fulfillment.
        4. Persist QuoteModel.
        5. Enforce KYC limits.
        """
        if fiat_amount is None and crypto_amount is None:
            raise ValueError("Either fiat_amount or crypto_amount must be provided")

        # Get effective rate (includes spread)
        effective_rate, spread_bps = await self.rate_service.get_quote_rate(
            crypto_asset, transaction_type.value, exchange
        )

        if fiat_amount is not None:
            fiat_amount = Decimal(str(fiat_amount))
            crypto_amount = fiat_amount / effective_rate
        else:
            crypto_amount = Decimal(str(crypto_amount))
            fiat_amount = crypto_amount * effective_rate

        # Simple fee model (can be made more sophisticated)
        fee_rate = Decimal("0.005")  # 0.5%
        fee_ngn = (fiat_amount * fee_rate).quantize(Decimal("0.01"))
        total_ngn = (fiat_amount + fee_ngn).quantize(Decimal("0.01"))

        # KYC limit enforcement (production critical)
        self._enforce_kyc_limits(fiat_amount, user_kyc_tier)

        # ILP cryptographic material
        condition, fulfillment = generate_ilp_condition()
        ilp_condition_b64 = condition.hex()  # store as hex for simplicity
        encrypted_fulfillment = encrypt_sensitive(fulfillment.hex())

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.quote_expiry_seconds)

        quote = QuoteModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            transaction_type=transaction_type.value,
            crypto_asset=crypto_asset.value,
            fiat_amount_ngn=fiat_amount,
            crypto_amount=crypto_amount.quantize(Decimal("0.00000001")),
            exchange_rate=effective_rate,
            spread_bps=spread_bps,
            fee_ngn=fee_ngn,
            total_ngn=total_ngn,
            exchange=exchange.value,
            ilp_condition=ilp_condition_b64,
            ilp_fulfillment_encrypted=encrypted_fulfillment,
            expires_at=expires_at,
            is_used=False,
        )

        db_session.add(quote)
        await db_session.flush()

        logger.info(
            f"Quote created: {quote.id} | {transaction_type.value} {crypto_asset.value} | "
            f"₦{fiat_amount} → {crypto_amount} | expires {expires_at}"
        )

        return QuoteResponse(
            id=quote.id,
            transaction_type=transaction_type,
            crypto_asset=crypto_asset,
            fiat_amount=fiat_amount,
            crypto_amount=crypto_amount,
            exchange_rate=effective_rate,
            spread_bps=spread_bps,
            fee_ngn=fee_ngn,
            total_ngn=total_ngn,
            expires_at=expires_at,
            ilp_condition=ilp_condition_b64,
        )

    def _enforce_kyc_limits(self, amount_ngn: Decimal, tier: KYCTier) -> None:
        tier_limits = {
            KYCTier.TIER_0: (settings.kyc_tier1_tx_limit_ngn / 2, settings.kyc_tier1_daily_limit_ngn / 2),
            KYCTier.TIER_1: (settings.kyc_tier1_tx_limit_ngn, settings.kyc_tier1_daily_limit_ngn),
            KYCTier.TIER_2: (settings.kyc_tier2_tx_limit_ngn, settings.kyc_tier2_daily_limit_ngn),
            KYCTier.TIER_3: (settings.kyc_tier3_tx_limit_ngn, settings.kyc_tier3_daily_limit_ngn),
        }
        tx_limit, _ = tier_limits.get(tier, (50000, 500000))

        if amount_ngn > tx_limit:
            raise TransactionLimitError(limit=float(tx_limit), tier=int(tier))

    async def get_quote(self, quote_id: str, db_session) -> Optional[QuoteModel]:
        from sqlalchemy import select
        result = await db_session.execute(select(QuoteModel).where(QuoteModel.id == quote_id))
        quote = result.scalar_one_or_none()
        if quote and quote.expires_at < datetime.now(timezone.utc):
            return None
        return quote

    async def mark_quote_used(self, quote_id: str, db_session) -> None:
        from sqlalchemy import select, update
        await db_session.execute(
            update(QuoteModel).where(QuoteModel.id == quote_id).values(is_used=True)
        )


_quote_service: Optional[QuoteService] = None


def get_quote_service() -> QuoteService:
    global _quote_service
    if _quote_service is None:
        _quote_service = QuoteService()
    return _quote_service
