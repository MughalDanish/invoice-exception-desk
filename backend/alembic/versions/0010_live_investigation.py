"""Enable live advisory modes and session-bound durable budgets only."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_live_investigation"
down_revision = "0009_durable_investigation"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("investigation_mock_only", "investigation_runs", type_="check")
    op.create_check_constraint(
        "investigation_mock_only", "investigation_runs", "mode IN ('mock','gemini')"
    )
    op.add_column("investigation_runs", sa.Column("requested_user_id", sa.Uuid()))
    op.add_column("investigation_runs", sa.Column("requested_session_id", sa.Uuid()))
    op.add_column(
        "investigation_runs",
        sa.Column(
            "budget_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade():
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT count(*) FROM investigation_runs "
            "WHERE mode <> 'mock' OR budget_metadata <> '{}'::jsonb"
        )
    ):
        raise RuntimeError("Live investigation history cannot be silently discarded")
    for name in ("budget_metadata", "requested_session_id", "requested_user_id"):
        op.drop_column("investigation_runs", name)
    op.drop_constraint("investigation_mock_only", "investigation_runs", type_="check")
    op.create_check_constraint("investigation_mock_only", "investigation_runs", "mode = 'mock'")
