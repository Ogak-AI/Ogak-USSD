"""Initial schema — all core tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phone_number", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("hashed_pin", sa.String(128), nullable=False),
        sa.Column("pin_salt", sa.String(64), nullable=False),
        sa.Column("language", sa.Enum("en", "pcm", "yo", "ha", "ig", name="language_enum"), default="en", nullable=False),
        sa.Column("kyc_tier", sa.Enum("0", "1", "2", "3", name="kyc_tier_enum"), default="1", nullable=False),
        sa.Column("bvn_encrypted", sa.Text, nullable=True),
        sa.Column("bvn_hash", sa.String(128), nullable=True, index=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("is_locked", sa.Boolean, default=False, nullable=False),
        sa.Column("pin_attempts", sa.Integer, default=0, nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_volume_ngn", sa.Numeric(20, 2), default=0, nullable=False),
        sa.Column("daily_volume_date", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Bank Accounts ─────────────────────────────────────────────────
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("bank_code", sa.String(10), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(10), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("is_verified", sa.Boolean, default=False, nullable=False),
        sa.Column("is_primary", sa.Boolean, default=False, nullable=False),
        sa.Column("paystack_recipient_code", sa.String(100), nullable=True),
        sa.Column("flutterwave_beneficiary_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bank_user_account", "bank_accounts", ["user_id", "bank_code", "account_number"], unique=True)

    # ── Exchange Accounts ─────────────────────────────────────────────
    op.create_table(
        "exchange_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("exchange", sa.Enum("quidax", "busha", "binance", name="exchange_enum"), nullable=False),
        sa.Column("exchange_user_id", sa.String(255), nullable=True),
        sa.Column("api_key_encrypted", sa.Text, nullable=False),
        sa.Column("api_secret_encrypted", sa.Text, nullable=False),
        sa.Column("is_verified", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_user", "exchange_accounts", ["user_id", "exchange"], unique=True)

    # ── Quotes ────────────────────────────────────────────────────────
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("transaction_type", sa.Enum("BUY", "SELL", name="tx_type_enum"), nullable=False),
        sa.Column("crypto_asset", sa.Enum("BTC", "USDT", "USDC", "ETH", "BNB", name="crypto_asset_enum"), nullable=False),
        sa.Column("fiat_amount_ngn", sa.Numeric(20, 2), nullable=False),
        sa.Column("crypto_amount", sa.Numeric(28, 8), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(20, 2), nullable=False),
        sa.Column("spread_bps", sa.Integer, nullable=False),
        sa.Column("fee_ngn", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_ngn", sa.Numeric(20, 2), nullable=False),
        sa.Column("exchange", sa.Enum("quidax", "busha", "binance", name="exchange_enum", create_constraint=False), nullable=False),
        sa.Column("ilp_condition", sa.String(64), nullable=False),
        sa.Column("ilp_fulfillment_encrypted", sa.Text, nullable=False),
        sa.Column("is_used", sa.Boolean, default=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quote_expires", "quotes", ["expires_at"])

    # ── Transactions ──────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("bank_account_id", sa.String(36), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("transaction_type", sa.Enum("BUY", "SELL", name="tx_type_enum", create_constraint=False), nullable=False),
        sa.Column("status", sa.Enum(
            "PENDING", "QUOTED", "CONFIRMED", "EXECUTING", "FIAT_SETTLED",
            "CRYPTO_SETTLED", "COMPLETED", "FAILED", "ROLLED_BACK", "EXPIRED", "CANCELLED",
            name="tx_status_enum",
        ), default="PENDING", nullable=False, index=True),
        sa.Column("crypto_asset", sa.Enum("BTC", "USDT", "USDC", "ETH", "BNB", name="crypto_asset_enum", create_constraint=False), nullable=False),
        sa.Column("fiat_amount_ngn", sa.Numeric(20, 2), nullable=False),
        sa.Column("crypto_amount", sa.Numeric(28, 8), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(20, 2), nullable=False),
        sa.Column("fee_ngn", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_ngn", sa.Numeric(20, 2), nullable=False),
        sa.Column("exchange", sa.Enum("quidax", "busha", "binance", name="exchange_enum", create_constraint=False), nullable=False),
        # Settlement
        sa.Column("bank_reference", sa.String(100), nullable=True),
        sa.Column("bank_provider", sa.String(20), nullable=True),
        sa.Column("fiat_settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exchange_order_id", sa.String(100), nullable=True),
        sa.Column("exchange_reference", sa.String(100), nullable=True),
        sa.Column("crypto_settled_at", sa.DateTime(timezone=True), nullable=True),
        # ILP
        sa.Column("ilp_packet_id", sa.String(36), nullable=True),
        sa.Column("ilp_condition", sa.String(64), nullable=True),
        sa.Column("ilp_fulfillment", sa.String(64), nullable=True),
        sa.Column("ilp_status", sa.String(20), nullable=True),
        # Failure
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("rollback_reference", sa.String(100), nullable=True),
        sa.Column("rollback_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tx_user_created", "transactions", ["user_id", "created_at"])
    op.create_index("ix_tx_status_created", "transactions", ["status", "created_at"])

    # ── Audit Logs ────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_audit_user_action", "audit_logs", ["user_id", "action"])
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("transactions")
    op.drop_table("quotes")
    op.drop_table("exchange_accounts")
    op.drop_table("bank_accounts")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS language_enum")
    op.execute("DROP TYPE IF EXISTS kyc_tier_enum")
    op.execute("DROP TYPE IF EXISTS tx_type_enum")
    op.execute("DROP TYPE IF EXISTS crypto_asset_enum")
    op.execute("DROP TYPE IF EXISTS exchange_enum")
    op.execute("DROP TYPE IF EXISTS tx_status_enum")
