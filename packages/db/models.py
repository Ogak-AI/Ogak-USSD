"""
Ogak Database Models
SQLAlchemy ORM models for all persistent entities.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.database import Base
from packages.shared.types import (
    CryptoAsset,
    Exchange,
    KYCTier,
    Language,
    TransactionStatus,
    TransactionType,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ===================================================================
# User
# ===================================================================

class UserModel(Base):
    """Registered Ogak user, identified by Nigerian phone number."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    hashed_pin: Mapped[str] = mapped_column(String(128), nullable=False)
    pin_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(
        Enum(Language, name="language_enum", create_constraint=True),
        default=Language.EN,
        nullable=False,
    )
    kyc_tier: Mapped[int] = mapped_column(
        Enum(KYCTier, name="kyc_tier_enum", create_constraint=True),
        default=KYCTier.TIER_1,
        nullable=False,
    )
    bvn_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    bvn_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pin_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    daily_volume_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    daily_volume_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    bank_accounts: Mapped[list["BankAccountModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    exchange_accounts: Mapped[list["ExchangeAccountModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    open_payments_incoming: Mapped[list["OpenPaymentsIncomingPaymentModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.phone_number} tier={self.kyc_tier}>"


# ===================================================================
# Bank Account
# ===================================================================

class BankAccountModel(Base):
    """Linked Nigerian bank account (verified via Paystack/Flutterwave)."""

    __tablename__ = "bank_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number: Mapped[str] = mapped_column(String(10), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Paystack recipient code for transfers out
    paystack_recipient_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Flutterwave beneficiary ID
    flutterwave_beneficiary_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="bank_accounts")

    __table_args__ = (
        Index("ix_bank_user_account", "user_id", "bank_code", "account_number", unique=True),
    )

    def __repr__(self) -> str:
        return f"<BankAccount {self.bank_name} ****{self.account_number[-4:]}>"


# ===================================================================
# Exchange Account
# ===================================================================

class ExchangeAccountModel(Base):
    """Linked crypto exchange / VASP account."""

    __tablename__ = "exchange_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(
        Enum(Exchange, name="exchange_enum", create_constraint=True), nullable=False
    )
    exchange_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="exchange_accounts")

    __table_args__ = (
        Index("ix_exchange_user", "user_id", "exchange", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ExchangeAccount {self.exchange}>"


# ===================================================================
# Quote
# ===================================================================

class QuoteModel(Base):
    """Locked conversion quote with ILP condition for atomic settlement."""

    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_type: Mapped[str] = mapped_column(
        Enum(TransactionType, name="tx_type_enum", create_constraint=True), nullable=False
    )
    crypto_asset: Mapped[str] = mapped_column(
        Enum(CryptoAsset, name="crypto_asset_enum", create_constraint=True), nullable=False
    )
    fiat_amount_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    crypto_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    spread_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    exchange: Mapped[str] = mapped_column(
        Enum(Exchange, name="exchange_enum", create_constraint=True), nullable=False
    )
    # ILP condition (base64-encoded SHA-256 hash)
    ilp_condition: Mapped[str] = mapped_column(String(64), nullable=False)
    # ILP fulfillment (base64-encoded preimage) — stored encrypted
    ilp_fulfillment_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_quote_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Quote {self.id[:8]} {self.transaction_type} {self.crypto_asset}>"


# ===================================================================
# Transaction
# ===================================================================

class TransactionModel(Base):
    """Full crypto-fiat transaction with dual-leg settlement tracking."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotes.id"), nullable=False
    )
    bank_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bank_accounts.id"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(
        Enum(TransactionType, name="tx_type_enum", create_constraint=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(TransactionStatus, name="tx_status_enum", create_constraint=True),
        default=TransactionStatus.PENDING,
        nullable=False,
        index=True,
    )
    crypto_asset: Mapped[str] = mapped_column(
        Enum(CryptoAsset, name="crypto_asset_enum", create_constraint=True), nullable=False
    )
    fiat_amount_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    crypto_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fee_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_ngn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    exchange: Mapped[str] = mapped_column(
        Enum(Exchange, name="exchange_enum", create_constraint=True), nullable=False
    )

    # ── Settlement References ─────────────────────────────────────────
    # Fiat leg (bank)
    bank_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # paystack/flutterwave
    fiat_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Crypto leg (exchange)
    exchange_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    crypto_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── ILP Tracking ──────────────────────────────────────────────────
    ilp_packet_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ilp_condition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ilp_fulfillment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ilp_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # prepared/fulfilled/rejected

    # ── Failure / Rollback ────────────────────────────────────────────
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rollback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_tx_user_created", "user_id", "created_at"),
        Index("ix_tx_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.reference} {self.status}>"


# ===================================================================
# Audit Log
# ===================================================================

class AuditLogModel(Base):
    """Immutable audit trail for compliance and debugging."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.resource_type}>"


# ===================================================================
# Open Payments Incoming Payment (production, persisted)
# ===================================================================

class OpenPaymentsIncomingPaymentModel(Base):
    """
    Persisted Open Payments incoming payment resource.

    This represents a receivable created via the Open Payments protocol
    (after a client obtained a grant and called create on the resource server).

    Fulfillment (updating received amounts + completed) is driven exclusively
    by the real settlement layer (ILP connector / orchestrator / payment listener),
    never by mocks or simulation.
    """

    __tablename__ = "open_payments_incoming_payments"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # full resource URL or stable id
    wallet_address: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Requested amount (from the create request)
    incoming_amount_value: Mapped[str] = mapped_column(String(64), nullable=False)
    incoming_asset_code: Mapped[str] = mapped_column(String(16), nullable=False)
    incoming_asset_scale: Mapped[int] = mapped_column(Integer, nullable=False)

    # What has actually been received
    received_amount_value: Mapped[str] = mapped_column(String(64), default="0", nullable=False)
    received_asset_code: Mapped[str] = mapped_column(String(16), nullable=False)
    received_asset_scale: Mapped[int] = mapped_column(Integer, nullable=False)

    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Optional linkage to how it was fulfilled (e.g. from ILP or external ref)
    fulfillment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["UserModel | None"] = relationship(back_populates="open_payments_incoming")

    __table_args__ = (
        Index("ix_op_incoming_user", "user_id"),
        Index("ix_op_incoming_expires", "expires_at"),
        Index("ix_op_incoming_wallet", "wallet_address"),
    )

    def __repr__(self) -> str:
        return f"<OpenPaymentsIncomingPayment {self.id[:16]}... completed={self.completed}>"
