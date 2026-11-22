"""Add bounded versioned evidence; do not change any financial tables."""

import sqlalchemy as sa

from alembic import op

revision = "0007_investigation_documents"
down_revision = "0006_investigation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigation_documents",
        sa.Column("source_id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("supplier_key", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("version >= 1", name="evidence_positive_version"),
        sa.CheckConstraint("kind IN ('PO', 'RECEIPT', 'EMAIL')", name="evidence_kind"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 1000", name="evidence_size"),
    )
    op.create_index(
        "ix_evidence_scope",
        "investigation_documents",
        ["invoice_id", "supplier_key", "source_id", "version"],
    )
    op.execute("""
        CREATE FUNCTION reject_investigation_document_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'Supporting evidence is append-only';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER investigation_documents_immutable
        BEFORE UPDATE OR DELETE ON investigation_documents
        FOR EACH ROW EXECUTE FUNCTION reject_investigation_document_mutation()
    """)


def downgrade():
    op.drop_table("investigation_documents")
    op.execute("DROP FUNCTION reject_investigation_document_mutation()")
