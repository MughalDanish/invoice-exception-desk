"""Versioned validation, reviewed payload hashes, and immutable ledger snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_review_ledger"
down_revision = "0002_processing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("validation_run_id", sa.Uuid()))
    op.add_column("validation_results", sa.Column("run_id", sa.Uuid()))
    op.create_index("ix_validation_results_run_id", "validation_results", ["run_id"])
    # Day 2 has one validation batch per invoice; keep its visible results intact.
    op.execute("UPDATE validation_results SET run_id = invoice_id")
    op.execute("""UPDATE invoices i SET validation_run_id = i.id
        WHERE EXISTS (SELECT 1 FROM validation_results v
                      WHERE v.invoice_id = i.id AND v.revision = i.revision)""")
    op.add_column("invoice_reviews", sa.Column("payload_sha256", sa.String(64)))
    op.add_column(
        "ledger_entries",
        sa.Column(
            "snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.execute("""UPDATE ledger_entries l SET snapshot = jsonb_build_object(
        'revision', i.revision, 'data', COALESCE(i.current_data, '{}'::jsonb))
        FROM invoices i WHERE i.id = l.invoice_id""")
    op.execute("""CREATE FUNCTION protect_review_and_ledger() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'Review and ledger entries are append-only'; END; $$""")
    for table in ("invoice_reviews", "ledger_entries"):
        op.execute(f"""CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE
            ON {table} FOR EACH ROW EXECUTE FUNCTION protect_review_and_ledger()""")


def downgrade():
    for table in ("invoice_reviews", "ledger_entries"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION protect_review_and_ledger()")
    op.drop_column("ledger_entries", "snapshot")
    op.drop_column("invoice_reviews", "payload_sha256")
    op.drop_index("ix_validation_results_run_id", table_name="validation_results")
    op.drop_column("validation_results", "run_id")
    op.drop_column("invoices", "validation_run_id")
