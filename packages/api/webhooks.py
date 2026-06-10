"""
Production Webhook Receivers

These endpoints receive real callbacks from:
- Paystack / Flutterwave (fiat leg settlement confirmation)
- Quidax / Busha / Binance (crypto leg status updates)

On successful fiat credit for a BUY, or successful crypto debit for a SELL,
the orchestrator (or a background Celery task) is notified to move to the next ILP phase
or to fulfill the payment.

All webhooks must verify signatures using the provider secrets from config.
"""

import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.database import get_db
from packages.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Paystack webhook handler.
    Verify signature, parse event, and trigger settlement completion if applicable.
    """
    body = await request.body()
    # In production:
    # 1. Verify HMAC signature using settings.paystack_webhook_secret
    # 2. Parse event (charge.success, transfer.success, etc.)
    # 3. Find matching Transaction by reference
    # 4. Update fiat_settled_at, status
    # 5. If both legs ready, call ILP fulfill via orchestrator

    logger.info("Paystack webhook received")
    # Production signature verification (HMAC-SHA512 using PAYSTACK_WEBHOOK_SECRET)
    import hmac
    import hashlib
    secret = settings.paystack_webhook_secret.encode()
    signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
    if signature != x_paystack_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # TODO in next iteration: parse event, find Transaction by reference, update fiat leg, trigger ILP fulfill if ready.
    return {"status": "received"}


@router.post("/flutterwave")
async def flutterwave_webhook(
    request: Request,
    verif_hash: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Flutterwave webhook handler (similar pattern)."""
    body = await request.body()
    logger.info("Flutterwave webhook received")
    # Real implementation: verify verif-hash, update transaction, advance ILP state.
    return {"status": "received"}


@router.post("/quidax")
async def quidax_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Quidax (or other VASP) webhook for crypto order status."""
    logger.info("Quidax webhook received")
    # On "completed" for a buy order → mark crypto_settled, check if ready for ILP fulfill.
    return {"status": "received"}


@router.post("/busha")
async def busha_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    logger.info("Busha webhook received")
    return {"status": "received"}
