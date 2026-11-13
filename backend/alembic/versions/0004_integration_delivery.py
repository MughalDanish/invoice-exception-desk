"""Durable integration idempotency receipts, including cross-source duplicates."""

import sqlalchemy as sa

from alembic import op

revision = "0004_integration_delivery"
down_revision = "0003_review_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("key_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
    )
    op.create_index(
        "ix_integration_deliveries_invoice_id", "integration_deliveries", ["invoice_id"]
    )


def downgrade():
    op.drop_table("integration_deliveries")
