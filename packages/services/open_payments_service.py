"""
Production Open Payments Service

Handles real (non-mock) lifecycle for Open Payments resources:
- Creating incoming payments from valid grants (receiver side)
- Retrieving them
- Fulfilling them when actual value arrives via settlement (ILP / connector / external listener)

All fulfillment must come from production paths only. No simulation.

This service works with the existing QuoteService, UserService, and
TransactionOrchestrator so that received Open Payments value can eventually
drive credits, on-ramps, or balance updates for Ogak users.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import OpenPaymentsIncomingPaymentModel, UserModel
from packages.services.quote_service import get_quote_service
from packages.shared.config import get_settings
from packages.shared.errors import OgakError
from packages.shared.types import OpenPaymentsIncomingPayment  # Pydantic response shape

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenPaymentsService:
    """
    Real Open Payments resource management.
    """

    def __init__(self):
        self.quote_service = get_quote_service()

    async def create_incoming_payment(
        self,
        *,
        wallet_address: str,
        incoming_amount: dict[str, Any],
        metadata: Optional[dict[str, Any]],
        expires_at: datetime,
        db_session: AsyncSession,
    ) -> OpenPaymentsIncomingPaymentModel:
        """
        Create and persist a new incoming payment resource.

        Called from the API after validating the access token from a grant.
        The caller is responsible for resolving the user (we attempt best-effort
        lookup here using the wallet address identifier).
        """
        # Try to resolve a user from the wallet address tail (phone or id)
        user_id: Optional[str] = None
        identifier = wallet_address.rstrip("/").split("/")[-1]
        if identifier:
            # Normalize a bit (phones often come without + in pointers)
            from packages.shared.crypto_utils import sanitize_phone
            try:
                phone = sanitize_phone(identifier)
                user = await self._get_user_by_phone(phone, db_session)
                if user:
                    user_id = user.id
            except Exception:
                pass  # non-fatal

        # Normalize incoming amount
        value = str(incoming_amount.get("value", "0"))
        asset_code = incoming_amount.get("assetCode", "NGN")
        asset_scale = int(incoming_amount.get("assetScale", 2))

        model = OpenPaymentsIncomingPaymentModel(
            id=f"{wallet_address}/incoming-payments/{uuid.uuid4()}" if not wallet_address.endswith("/incoming-payments/") else f"{wallet_address}{uuid.uuid4()}",
            wallet_address=wallet_address,
            user_id=user_id,
            incoming_amount_value=value,
            incoming_asset_code=asset_code,
            incoming_asset_scale=asset_scale,
            received_amount_value="0",
            received_asset_code=asset_code,
            received_asset_scale=asset_scale,
            completed=False,
            metadata=metadata or {},
            expires_at=expires_at,
        )

        db_session.add(model)
        await db_session.flush()

        logger.info(
            "Open Payments incoming payment persisted",
            extra={
                "op_ip_id": model.id,
                "wallet": wallet_address,
                "user_id": user_id,
                "incoming_value": value,
            },
        )
        return model

    async def get_incoming_payment(
        self, incoming_payment_id: str, db_session: AsyncSession
    ) -> Optional[OpenPaymentsIncomingPaymentModel]:
        """Fetch by the stable id (full URL or the uuid tail)."""
        # Try exact match first
        result = await db_session.execute(
            select(OpenPaymentsIncomingPaymentModel).where(
                OpenPaymentsIncomingPaymentModel.id == incoming_payment_id
            )
        )
        ip = result.scalar_one_or_none()
        if ip:
            return ip

        # Try suffix match (in case client passed only the uuid part)
        if "/" not in incoming_payment_id:
            result = await db_session.execute(
                select(OpenPaymentsIncomingPaymentModel).where(
                    OpenPaymentsIncomingPaymentModel.id.like(f"%/{incoming_payment_id}")
                )
            )
            return result.scalar_one_or_none()

        return None

    async def fulfill_incoming_payment(
        self,
        *,
        incoming_payment_id: str,
        received_value: str,
        fulfillment_reference: Optional[str] = None,
        db_session: AsyncSession,
    ) -> OpenPaymentsIncomingPaymentModel:
        """
        Mark an incoming payment as (partially or fully) received with real value.

        This must ONLY be called from production settlement code:
        - Your ILP connector when it sees a matching incoming packet
        - A listener for direct OP/ILP settlement
        - An internal credit worker after bank/exchange confirmation for an OP-triggered flow

        After updating the record, this method can trigger downstream effects
        (e.g. crediting the user, creating a transaction record, notifying via USSD/SMS).

        Returns the updated model.
        """
        ip = await self.get_incoming_payment(incoming_payment_id, db_session)
        if not ip:
            raise OgakError(f"Open Payments incoming payment not found: {incoming_payment_id}")

        if ip.completed:
            logger.warning("Fulfill called on already completed incoming payment", extra={"id": ip.id})
            return ip

        # Update received state
        ip.received_amount_value = str(received_value)
        ip.received_asset_code = ip.incoming_asset_code
        ip.received_asset_scale = ip.incoming_asset_scale
        ip.completed = True
        ip.fulfilled_at = datetime.now(timezone.utc)
        if fulfillment_reference:
            ip.fulfillment_reference = fulfillment_reference

        await db_session.flush()

        logger.info(
            "Open Payments incoming payment fulfilled (real settlement)",
            extra={
                "op_ip_id": ip.id,
                "received_value": received_value,
                "user_id": ip.user_id,
                "reference": fulfillment_reference,
            },
        )

        # === Real downstream credit hook (production only) ===
        # Here you can:
        # - Create a credit Transaction (special type or via a receive flow)
        # - Call orchestrator in a "receive credit" mode
        # - Credit an internal balance
        # - Queue a Celery task
        #
        # Example skeleton (uncomment/adapt when you have the credit path):
        #
        # if ip.user_id:
        #     try:
        #         # from packages.services.transaction_orchestrator import get_orchestrator
        #         # orchestrator = get_orchestrator()
        #         # await orchestrator.credit_via_open_payments(
        #         #     user_id=ip.user_id,
        #         #     amount=Decimal(received_value),
        #         #     asset_code=ip.received_asset_code,
        #         #     op_incoming_id=ip.id,
        #         #     db_session=db_session,
        #         # )
        #         pass
        #     except Exception as e:
        #         logger.exception("Downstream credit after OP fulfill failed (will retry via worker)")

        return ip

    async def _get_user_by_phone(
        self, phone_number: str, db_session: AsyncSession
    ) -> Optional[UserModel]:
        from packages.services.user_service import get_user_service

        user_service = get_user_service()
        return await user_service.get_user_by_phone(phone_number, db_session)


_open_payments_service: Optional[OpenPaymentsService] = None


def get_open_payments_service() -> OpenPaymentsService:
    global _open_payments_service
    if _open_payments_service is None:
        _open_payments_service = OpenPaymentsService()
    return _open_payments_service
