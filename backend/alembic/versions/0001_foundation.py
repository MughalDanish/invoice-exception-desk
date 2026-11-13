"""Initial invoice, vendor, review, ledger and audit schema."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade():
    op.create_table(
        "vendors",
        *identity(),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("expected_currency", sa.String(3)),
        sa.Column("baseline_amount_limit", sa.Numeric(18, 2)),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("normalized_name", name="uq_vendors_normalized_name"),
    )
    op.create_table(
        "invoices",
        *identity(),
        sa.Column(
            "source",
            sa.Enum(
                "api", "gmail", "fixture", name="source", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("source_message_id", sa.String(255)),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RECEIVED",
                "EXTRACTING",
                "NEEDS_REVIEW",
                "READY_TO_POST",
                "POSTED",
                "REJECTED",
                "EXTRACTION_FAILED",
                name="invoicestatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("extracted_data", postgresql.JSONB()),
        sa.Column("current_data", postgresql.JSONB()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), sa.ForeignKey("vendors.id")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("sha256", name="uq_invoices_sha256"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint("byte_size > 0", name="positive_size"),
    )
    op.create_index(
        "uq_invoices_source_delivery",
        "invoices",
        ["source", "source_message_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("source_message_id IS NOT NULL"),
    )
    op.create_index("ix_invoices_status_created_at", "invoices", ["status", "created_at"])
    op.create_table(
        "validation_results",
        *identity(),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(80), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "INFO",
                "WARNING",
                "BLOCKER",
                name="severity",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expected", postgresql.JSONB()),
        sa.Column("observed", postgresql.JSONB()),
    )
    op.create_index("ix_validation_results_invoice_id", "validation_results", ["invoice_id"])
    op.create_table(
        "invoice_reviews",
        *identity(),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "APPROVE", "REJECT", name="decision", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "invoice_id", "revision", "decision", name="uq_invoice_reviews_invoice_id"
        ),
    )
    op.create_index("ix_invoice_reviews_invoice_id", "invoice_reviews", ["invoice_id"])
    op.create_table(
        "ledger_entries",
        *identity(),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("invoice_number_normalized", sa.String(200), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("posted_by", sa.String(200), nullable=False),
        sa.UniqueConstraint("invoice_id", name="uq_ledger_entries_invoice_id"),
        sa.UniqueConstraint(
            "vendor_id", "invoice_number_normalized", name="uq_ledger_vendor_number"
        ),
    )
    op.create_table(
        "audit_events",
        *identity(),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id")),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_audit_events_invoice_id", "audit_events", ["invoice_id"])
    op.execute("""
        CREATE FUNCTION protect_audit_events() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION protect_audit_events()
    """)


def downgrade():
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION protect_audit_events()")
    for table in ("ledger_entries", "invoice_reviews", "validation_results", "invoices", "vendors"):
        op.drop_table(table)
