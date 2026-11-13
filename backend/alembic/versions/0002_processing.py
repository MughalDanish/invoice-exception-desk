"""Persist extraction attempts and normalized invoice identity."""

import sqlalchemy as sa

from alembic import op

revision = "0002_processing"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("normalized_vendor_name", sa.String(200)))
    op.add_column("invoices", sa.Column("normalized_invoice_number", sa.String(200)))
    op.add_column(
        "invoices",
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_invoices_business_identity",
        "invoices",
        ["normalized_vendor_name", "normalized_invoice_number"],
    )
    op.create_table(
        "processing_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                name="attemptstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.UniqueConstraint("invoice_id", "ordinal", name="uq_processing_attempts_invoice_id"),
        sa.CheckConstraint("ordinal >= 1", name="positive_ordinal"),
    )
    op.create_index("ix_processing_attempts_invoice_id", "processing_attempts", ["invoice_id"])


def downgrade():
    op.drop_table("processing_attempts")
    op.drop_index("ix_invoices_business_identity", table_name="invoices")
    op.drop_column("invoices", "review_required")
    op.drop_column("invoices", "normalized_invoice_number")
    op.drop_column("invoices", "normalized_vendor_name")
