"""
Ogak Admin Dashboard
FastAPI application serving a real-time monitoring dashboard
with WebSocket updates for transaction feeds and system health.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.config import get_settings
from packages.db.database import get_db, async_session_factory
from packages.db.models import (
    UserModel,
    TransactionModel,
    QuoteModel,
    AuditLogModel,
)
from packages.shared.types import TransactionStatus, TransactionType

logger = structlog.get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title="Ogak Admin Dashboard",
    version="1.0.0",
    docs_url="/admin/docs",
)

TEMPLATES_DIR = Path(__file__).parent / "templates"


# ── WebSocket Connection Manager ──────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("admin_ws_connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.info("admin_ws_disconnected", total=len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


ws_manager = ConnectionManager()


# ── Dashboard HTML ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Serve the admin dashboard HTML."""
    template_path = TEMPLATES_DIR / "dashboard.html"
    if not template_path.exists():
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=500)
    return HTMLResponse(template_path.read_text(encoding="utf-8"))


# ── Real-Time Stats API ──────────────────────────────────────────────

@app.get("/admin/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get real-time platform statistics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total users
    user_count = await db.scalar(select(func.count(UserModel.id)))

    # Today's transactions
    today_tx_count = await db.scalar(
        select(func.count(TransactionModel.id)).where(
            TransactionModel.created_at >= today_start
        )
    )

    # Today's volume (NGN)
    today_volume = await db.scalar(
        select(func.coalesce(func.sum(TransactionModel.total_ngn), 0)).where(
            and_(
                TransactionModel.created_at >= today_start,
                TransactionModel.status == TransactionStatus.COMPLETED,
            )
        )
    )

    # Today's revenue (fees)
    today_revenue = await db.scalar(
        select(func.coalesce(func.sum(TransactionModel.fee_ngn), 0)).where(
            and_(
                TransactionModel.created_at >= today_start,
                TransactionModel.status == TransactionStatus.COMPLETED,
            )
        )
    )

    # Transaction status breakdown (last 24h)
    status_query = (
        select(
            TransactionModel.status,
            func.count(TransactionModel.id),
        )
        .where(TransactionModel.created_at >= now - timedelta(hours=24))
        .group_by(TransactionModel.status)
    )
    status_rows = (await db.execute(status_query)).all()
    status_breakdown = {str(row[0]): row[1] for row in status_rows}

    # Buy vs Sell breakdown (last 24h)
    type_query = (
        select(
            TransactionModel.transaction_type,
            func.count(TransactionModel.id),
            func.coalesce(func.sum(TransactionModel.total_ngn), 0),
        )
        .where(TransactionModel.created_at >= now - timedelta(hours=24))
        .group_by(TransactionModel.transaction_type)
    )
    type_rows = (await db.execute(type_query)).all()
    type_breakdown = {
        str(row[0]): {"count": row[1], "volume_ngn": float(row[2])}
        for row in type_rows
    }

    # Pending / active transactions
    pending_count = await db.scalar(
        select(func.count(TransactionModel.id)).where(
            TransactionModel.status.in_([
                TransactionStatus.PENDING,
                TransactionStatus.CONFIRMED,
                TransactionStatus.EXECUTING,
            ])
        )
    )

    # Failed transactions (last 24h)
    failed_count = await db.scalar(
        select(func.count(TransactionModel.id)).where(
            and_(
                TransactionModel.created_at >= now - timedelta(hours=24),
                TransactionModel.status.in_([
                    TransactionStatus.FAILED,
                    TransactionStatus.ROLLED_BACK,
                ]),
            )
        )
    )

    return {
        "timestamp": now.isoformat(),
        "users": {"total": user_count or 0},
        "transactions": {
            "today_count": today_tx_count or 0,
            "today_volume_ngn": float(today_volume or 0),
            "today_revenue_ngn": float(today_revenue or 0),
            "pending": pending_count or 0,
            "failed_24h": failed_count or 0,
            "status_breakdown": status_breakdown,
            "type_breakdown": type_breakdown,
        },
    }


@app.get("/admin/api/transactions")
async def get_transactions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get recent transactions with optional status filter."""
    query = select(TransactionModel).order_by(TransactionModel.created_at.desc())

    if status:
        query = query.where(TransactionModel.status == status)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    transactions = result.scalars().all()

    return {
        "transactions": [
            {
                "id": tx.id,
                "reference": tx.reference,
                "type": str(tx.transaction_type),
                "status": str(tx.status),
                "crypto_asset": str(tx.crypto_asset),
                "fiat_amount_ngn": float(tx.fiat_amount_ngn),
                "crypto_amount": float(tx.crypto_amount),
                "fee_ngn": float(tx.fee_ngn),
                "exchange": str(tx.exchange),
                "bank_reference": tx.bank_reference,
                "exchange_reference": tx.exchange_reference,
                "ilp_status": tx.ilp_status,
                "failure_reason": tx.failure_reason,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
                "completed_at": tx.completed_at.isoformat() if tx.completed_at else None,
            }
            for tx in transactions
        ],
        "limit": limit,
        "offset": offset,
    }


@app.get("/admin/api/audit-log")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get recent audit log entries."""
    query = select(AuditLogModel).order_by(AuditLogModel.timestamp.desc())

    if action:
        query = query.where(AuditLogModel.action == action)

    query = query.limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ]
    }


# ── WebSocket ─────────────────────────────────────────────────────────

@app.websocket("/admin/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time dashboard updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive any control messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Health ────────────────────────────────────────────────────────────

@app.get("/admin/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "ogak-admin"}


def start() -> None:
    """Entry point for ogak-admin command."""
    import uvicorn
    uvicorn.run(
        "packages.admin.main:app",
        host="0.0.0.0",
        port=settings.admin_port,
        reload=settings.is_development,
    )
