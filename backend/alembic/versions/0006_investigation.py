"""Add isolated advisory investigation records; preserve all Phase 1 tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_investigation"
down_revision = "0005_cookie_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("validation_batch_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("provider_version", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("report", postgresql.JSONB()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("invoice_id", "idempotency_key", name="uq_investigation_request"),
        sa.CheckConstraint("revision >= 1", name="investigation_positive_revision"),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED', 'STALE')", name="investigation_status"
        ),
        sa.CheckConstraint("mode = 'mock'", name="investigation_mock_only"),
    )
    op.create_index(
        "ix_investigation_invoice_created", "investigation_runs", ["invoice_id", "created_at"]
    )


def downgrade():
    op.drop_table("investigation_runs")
