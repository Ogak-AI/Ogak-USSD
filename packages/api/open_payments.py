"""
Open Payments API Implementation (improved)

Makes Ogak a better Open Payments citizen so external clients (wallets, the official
workshop script, Rafiki instances, other connectors) can:

- Resolve Ogak user wallet addresses
- Request non-interactive grants for creating incoming payments
- Create incoming payments (the "payment pointer" that can receive value)
- Query incoming payment status

This implementation focuses on the **receiver side** (being paid), which is the most
valuable for Ogak's use case (external parties sending value that can on-ramp into
Nigerian users via the existing USSD + ILP atomic flows).

Inspired by the official workshop:
https://github.com/interledger/open-payments-workshop

For full spec compliance (production), consider:
- Persisting grants + incoming payments (new DB tables)
- Proper signed access tokens / GNAP continuation
- A dedicated auth server (or integrate Rafiki)
- Supporting outgoing payments (Ogak users paying out via OP)
"""

import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.database import get_db
from packages.services.open_payments_service import get_open_payments_service
from packages.shared.config import get_settings
from packages.shared.types import (
    OpenPaymentsWalletAddress,
    OpenPaymentsGrantRequest,
    OpenPaymentsGrantResponse,
    OpenPaymentsAccessToken,
    OpenPaymentsIncomingPayment,
    OpenPaymentsIncomingPaymentCreateRequest,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/open-payments", tags=["open-payments"])


def _get_public_base_url(request: Optional[Request] = None) -> str:
    """
    Best-effort public base for constructing wallet/auth/resource URLs.
    Priority:
      1. Explicit OP_PUBLIC_BASE_URL / op_public_base_url setting (recommended for prod)
      2. X-Forwarded-* headers (when behind nginx/traefik/etc.)
      3. Hardcoded localhost dev default
    """
    # 1. Config / env setting (best for production)
    base = getattr(settings, "op_public_base_url", None)
    if base:
        return base.rstrip("/")

    # 2. Reverse proxy headers
    if request is not None:
        forwarded = request.headers.get("x-forwarded-proto")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            scheme = forwarded or "https"
            return f"{scheme}://{host}".rstrip("/")

    # 3. Dev fallback
    return "http://localhost:8001"


def _build_wallet_url(base: str, identifier: str) -> str:
    safe = identifier.replace("+", "").replace(" ", "")
    return f"{base}/api/v1/open-payments/wallet-addresses/{safe}"


def _build_auth_server(base: str) -> str:
    return f"{base}/api/v1/open-payments/auth"


def _build_resource_server(base: str) -> str:
    return f"{base}/api/v1/open-payments/resource"


def _generate_access_token() -> str:
    return "op_" + secrets.token_urlsafe(24)


async def _redis_client():
    """Get Redis client instance."""
    return AsyncRedis.from_url(settings.redis_url, decode_responses=True)


async def _is_valid_incoming_grant_token(token: str, expected_wallet: Optional[str] = None) -> bool:
    """Check if a grant token is valid. Uses Redis for distributed state."""
    redis = await _redis_client()
    try:
        grant_json = await redis.get(f"op:grant:{token}")
        if not grant_json:
            return False
        
        grant = json.loads(grant_json)
        if grant.get("type") != "incoming-payment":
            return False
        if expected_wallet and grant.get("wallet_address") != expected_wallet:
            return False
        return True
    finally:
        await redis.close()


# ═══════════════════════════════════════════════════════════════════
# Wallet Address (public, what clients call first)
# ═══════════════════════════════════════════════════════════════════

@router.get("/wallet-addresses/{identifier}", response_model=OpenPaymentsWalletAddress)
async def get_wallet_address(
    identifier: str, request: Request, db: AsyncSession = Depends(get_db)
) -> OpenPaymentsWalletAddress:
    """
    Return a standard Open Payments Wallet Address document.

    Clients (including the workshop script) do:
        const wa = await client.walletAddress.get({ url: "..." })

    This is the entry point for discovery + all subsequent grant/resource calls.

    Identifier can be:
      - a phone number (with or without +)
      - a user id / account reference
    """
    base = _get_public_base_url(request)

    # Normalize identifier (phone or id)
    ident = identifier.strip()
    if ident.startswith("0") and len(ident) == 11:  # naive NG local
        ident = "+234" + ident[1:]

    public_name = "Ogak User"
    asset_code = "NGN"
    asset_scale = 2

    try:
        from packages.services.user_service import get_user_service
        user_service = get_user_service()
        user = await user_service.get_user_by_phone(ident, db)
        if user:
            public_name = user.full_name or f"Ogak {ident[-4:]}"
    except Exception:
        pass  # non-fatal for public endpoint

    wallet_id = _build_wallet_url(base, ident)

    return OpenPaymentsWalletAddress(
        id=wallet_id,
        publicName=public_name,
        assetCode=asset_code,
        assetScale=asset_scale,
        authServer=_build_auth_server(base),
        resourceServer=_build_resource_server(base),
    )


# ═══════════════════════════════════════════════════════════════════
# Account discovery (kept for backward + convenience)
# ═══════════════════════════════════════════════════════════════════

class AccountDiscoveryRequest(BaseModel):
    identifier: str


class AccountDiscoveryResponse(BaseModel):
    pointer: str
    account_id: str
    assetCode: str = "NGN"
    assetScale: int = 2


@router.post("/accounts/discovery", response_model=AccountDiscoveryResponse)
async def discover_account(
    request: AccountDiscoveryRequest, req: Request, db: AsyncSession = Depends(get_db)
) -> AccountDiscoveryResponse:
    """
    Convenience discovery (Ogak-specific).

    For full Open Payments interop, prefer resolving via the wallet-addresses GET above
    (standard clients call GET on the payment pointer / wallet URL directly).
    """
    identifier = request.identifier.strip()
    user_service = get_user_service()
    user = await user_service.get_user_by_phone(identifier, db)

    account_id = user.id if user else f"unknown-{identifier}"
    pointer = _build_wallet_url(_get_public_base_url(req), identifier)

    return AccountDiscoveryResponse(
        pointer=pointer,
        account_id=account_id,
        assetCode="NGN",
        assetScale=2,
    )


# ═══════════════════════════════════════════════════════════════════
# Authorization Server (GNAP / grant requests)
# This is what goes into walletAddress.authServer
# ═══════════════════════════════════════════════════════════════════

@router.post("/auth/grants", response_model=OpenPaymentsGrantResponse)
async def request_grant(body: OpenPaymentsGrantRequest, request: Request) -> OpenPaymentsGrantResponse:
    """
    Minimal GNAP-style grant request handler for Open Payments.

    The workshop (and real OP clients) call this on the authServer with:

    {
      "access_token": {
        "access": [
          { "type": "incoming-payment", "actions": ["create", "read"] }
        ]
      }
    }

    For non-interactive grants (no "interact" key) we return a finalized grant + access token
    immediately. This is the common path for creating incoming payments on a receiver.
    """
    access = body.access_token or {}
    requested_access = access.get("access", [])

    is_incoming = any(
        a.get("type") == "incoming-payment" and "create" in (a.get("actions") or [])
        for a in requested_access
    )

    if not is_incoming:
        # We only support simple incoming-payment grants in this minimal implementation.
        # Outgoing (sender side) would require interactive flow + user consent UI.
        raise HTTPException(
            status_code=501,
            detail="Only non-interactive incoming-payment grants are supported on this server.",
        )

    # Determine the target wallet if the client passed an identifier (some clients do via limits or future extensions)
    # For now we accept any and the token will be usable for creates against any of our wallet addresses.
    # A stricter impl would validate against a specific resource owner.

    token_value = _generate_access_token()

    grant_info = {
        "token": token_value,
        "wallet_address": None,  # can be bound later on first use or from client info
        "type": "incoming-payment",
        "actions": ["create", "read"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_request": body.model_dump() if hasattr(body, "model_dump") else dict(body),
    }
    
    # Store grant in Redis with 1-hour expiration
    redis = await _redis_client()
    try:
        await redis.setex(f"op:grant:{token_value}", 3600, json.dumps(grant_info))
    finally:
        await redis.close()

    logger.info("Issued non-interactive incoming-payment grant", extra={"token_prefix": token_value[:10]})

    return OpenPaymentsGrantResponse(
        access_token=OpenPaymentsAccessToken(
            value=token_value,
            access=requested_access,
            expires_in=3600
        )
    )


# ═══════════════════════════════════════════════════════════════════
# Resource Server - Incoming Payments
# This is what goes into walletAddress.resourceServer
# ═══════════════════════════════════════════════════════════════════

@router.post("/resource/incoming-payments", response_model=OpenPaymentsIncomingPayment)
async def create_incoming_payment(
    body: OpenPaymentsIncomingPaymentCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OpenPaymentsIncomingPayment:
    """
    Create an incoming payment (the actual "invoice" / receivable).

    Called by an Open Payments client AFTER obtaining a valid access token from the grant.

    The Authorization header must be: Bearer <access_token_from_grant>

    This is fully persisted. Fulfillment happens only via real settlement.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth.split(" ", 1)[1].strip()

    if not _is_valid_incoming_grant_token(token):
        raise HTTPException(status_code=403, detail="Invalid or expired access token")

    target_wallet = body.walletAddress
    incoming_amount = body.incomingAmount or {
        "value": "0",
        "assetCode": "NGN",
        "assetScale": 2,
    }

    now = datetime.now(timezone.utc)
    expires_at = body.expiresAt or (now + timedelta(hours=24))

    service = get_open_payments_service()
    model = await service.create_incoming_payment(
        wallet_address=target_wallet,
        incoming_amount=incoming_amount,
        metadata=body.metadata or {"description": "Open Payments incoming to Ogak"},
        expires_at=expires_at,
        db_session=db,
    )

    # Convert model to the Pydantic response shape expected by clients
    return OpenPaymentsIncomingPayment(
        id=model.id,
        walletAddress=model.wallet_address,
        incomingAmount={
            "value": model.incoming_amount_value,
            "assetCode": model.incoming_asset_code,
            "assetScale": model.incoming_asset_scale,
        },
        receivedAmount={
            "value": model.received_amount_value,
            "assetCode": model.received_asset_code,
            "assetScale": model.received_asset_scale,
        },
        completed=model.completed,
        metadata=model.metadata,
        createdAt=model.created_at,
        expiresAt=model.expires_at,
        updatedAt=model.updated_at,
    )


@router.get("/resource/incoming-payments/{payment_id:path}", response_model=OpenPaymentsIncomingPayment)
async def get_incoming_payment(
    payment_id: str, request: Request, db: AsyncSession = Depends(get_db)
) -> OpenPaymentsIncomingPayment:
    """
    Retrieve status of a previously created incoming payment.
    Real clients poll or use webhooks / STREAM to know when money arrived.
    Fulfillment status is only updated by real settlement.
    """
    service = get_open_payments_service()
    model = await service.get_incoming_payment(payment_id, db)
    if not model:
        raise HTTPException(status_code=404, detail="Incoming payment not found")

    return OpenPaymentsIncomingPayment(
        id=model.id,
        walletAddress=model.wallet_address,
        incomingAmount={
            "value": model.incoming_amount_value,
            "assetCode": model.incoming_asset_code,
            "assetScale": model.incoming_asset_scale,
        },
        receivedAmount={
            "value": model.received_amount_value,
            "assetCode": model.received_asset_code,
            "assetScale": model.received_asset_scale,
        },
        completed=model.completed,
        metadata=model.metadata,
        createdAt=model.created_at,
        expiresAt=model.expires_at,
        updatedAt=model.updated_at,
    )


# ═══════════════════════════════════════════════════════════════════
# Real fulfillment path (no simulation)
# ═══════════════════════════════════════════════════════════════════
#
# When a real Open Payments payment arrives (via ILP STREAM, another connector,
# or direct settlement), the receiving side (your ILP connector / settlement
# engine / orchestrator) is responsible for:
#
#   1. Matching the incoming packet/transfer to a previously created
#      OpenPaymentsIncomingPayment (by incoming payment id / condition / etc.).
#   2. Updating the receivedAmount and completed flag on the record.
#   3. Triggering the appropriate credit / on-ramp flow for the linked user
#      (using TransactionOrchestrator + QuoteService, or a dedicated credit path).
#
# There are no mock or simulate endpoints. All state transitions for
# received funds must come from production settlement paths only.


# ═══════════════════════════════════════════════════════════════════
# Additional endpoints (quotes)
# ═══════════════════════════════════════════════════════════════════

@router.post("/quotes")
async def create_quote(
    source_asset_code: str,
    destination_asset_code: str,
    receiver: str,
    amount: Decimal,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Open Payments compatible quote endpoint.

    For external clients wanting to pay *into* Ogak users, this can return
    a quote for receiving NGN (or converting on the way).

    Currently a thin wrapper. For full production use with external parties,
    you will likely want a dedicated unauthenticated or lightly-authenticated
    quote flow that does not require an Ogak user context, or maps the
    receiver pointer to a user first.
    """
    from packages.services.rate_service import get_rate_service

    rate_service = get_rate_service()

    try:
        # Best effort: use live rate for NGN <-> the destination asset if known.
        # This is intentionally simplified. Real OP quote semantics may differ
        # depending on whether the client is doing a pure receive or a conversion.
        effective_rate, _ = await rate_service.get_quote_rate(
            # We treat destination as the "crypto" side for rate purposes if it matches
            # our enum; otherwise fall back.
            destination_asset_code if destination_asset_code in ["BTC", "USDT", "USDC", "ETH", "BNB"] else "USDT",
            "BUY",  # receiving into Ogak is conceptually like a buy credit for the user
            "quidax",  # or make configurable
        )
    except Exception:
        effective_rate = Decimal("1")

    estimated = (amount * Decimal(str(effective_rate)) * Decimal("0.99")).quantize(Decimal("0.01"))

    return {
        "id": str(uuid.uuid4()),
        "sourceAssetCode": source_asset_code,
        "destinationAssetCode": destination_asset_code,
        "receiver": receiver,
        "amount": str(amount),
        "estimatedDeliveryAmount": str(estimated),
        "exchangeRate": str(effective_rate),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "note": "Production integration should use full QuoteService + ILP condition when exposing quotes to external OP clients.",
    }


# ═══════════════════════════════════════════════════════════════════
# Internal settlement hook (real fulfillment only — no public simulation)
# ═══════════════════════════════════════════════════════════════════

class InternalFulfillRequest(BaseModel):
    received_value: str
    fulfillment_reference: Optional[str] = None


@router.post("/internal/incoming-payments/{payment_id:path}/fulfill", include_in_schema=False)
async def internal_fulfill_incoming_payment(
    payment_id: str,
    body: InternalFulfillRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    INTERNAL ONLY.

    Called by your ILP connector, settlement worker, or payment listener
    when real value for this Open Payments incoming payment has arrived.

    This is the production path. It updates the persisted record and can
    trigger credit to the user.

    Do not expose this publicly. Protect it with network controls,
    mTLS, or a separate internal API gateway.
    """
    service = get_open_payments_service()
    model = await service.fulfill_incoming_payment(
        incoming_payment_id=payment_id,
        received_value=body.received_value,
        fulfillment_reference=body.fulfillment_reference,
        db_session=db,
    )

    return {
        "success": True,
        "incoming_payment_id": model.id,
        "completed": model.completed,
        "received_amount": {
            "value": model.received_amount_value,
            "assetCode": model.received_asset_code,
            "assetScale": model.received_asset_scale,
        },
        "user_id": model.user_id,
        "fulfilled_at": model.fulfilled_at.isoformat() if model.fulfilled_at else None,
    }


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    # Lightweight count for observability (real data only)
    from sqlalchemy import func, select
    from packages.db.models import OpenPaymentsIncomingPaymentModel

    try:
        result = await db.execute(select(func.count()).select_from(OpenPaymentsIncomingPaymentModel))
        ip_count = result.scalar_one()
    except Exception:
        ip_count = -1  # indicates DB not yet migrated or transient issue

    # Count active grants in Redis
    active_grants_count = 0
    try:
        redis = await _redis_client()
        try:
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match="op:grant:*", count=100)
                active_grants_count += len(keys)
                if cursor == 0:
                    break
        finally:
            await redis.close()
    except Exception:
        active_grants_count = -1

    return {
        "status": "healthy",
        "service": "ogak-open-payments",
        "version": "2.0.0",
        "features": ["wallet-addresses", "grants (incoming)", "incoming-payments (resource server, db-backed)"],
        "active_grants": active_grants_count,
        "persisted_incoming_payments": ip_count,
        "note": "Fulfillment only via real settlement. Run the 002 migration for the table.",
    }
