"""Add open_payments_incoming_payments table for real Open Payments receivables

Revision ID: 002_add_open_payments_incoming_payments
Revises: 001_initial
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_add_open_payments_incoming_payments"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "open_payments_incoming_payments",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("wallet_address", sa.String(255), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Requested incoming amount
        sa.Column("incoming_amount_value", sa.String(64), nullable=False),
        sa.Column("incoming_asset_code", sa.String(16), nullable=False),
        sa.Column("incoming_asset_scale", sa.Integer, nullable=False),
        # Received so far
        sa.Column("received_amount_value", sa.String(64), nullable=False, server_default="0"),
        sa.Column("received_asset_code", sa.String(16), nullable=False),
        sa.Column("received_asset_scale", sa.Integer, nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Fulfillment linkage (real settlement only)
        sa.Column("fulfillment_reference", sa.String(100), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_op_incoming_user",
        "open_payments_incoming_payments",
        ["user_id"],
    )
    op.create_index(
        "ix_op_incoming_expires",
        "open_payments_incoming_payments",
        ["expires_at"],
    )
    op.create_index(
        "ix_op_incoming_wallet",
        "open_payments_incoming_payments",
        ["wallet_address"],
    )


def downgrade() -> None:
    op.drop_index("ix_op_incoming_wallet", table_name="open_payments_incoming_payments")
    op.drop_index("ix_op_incoming_expires", table_name="open_payments_incoming_payments")
    op.drop_index("ix_op_incoming_user", table_name="open_payments_incoming_payments")
    op.drop_table("open_payments_incoming_payments")
