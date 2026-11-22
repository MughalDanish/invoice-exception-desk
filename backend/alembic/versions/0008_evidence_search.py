"""Index bounded supporting evidence without changing its immutable records."""

from alembic import op

revision = "0008_evidence_search"
down_revision = "0007_investigation_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX ix_evidence_fts ON investigation_documents "
        "USING gin (to_tsvector('english', content))"
    )


def downgrade():
    op.drop_index("ix_evidence_fts", table_name="investigation_documents")
