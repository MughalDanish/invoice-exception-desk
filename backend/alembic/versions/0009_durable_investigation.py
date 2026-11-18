"""Add durable queue ownership/events; financial tables are untouched."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009_durable_investigation"
down_revision = "0008_evidence_search"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("investigation_status", "investigation_runs", type_="check")
    op.create_check_constraint(
        "investigation_status",
        "investigation_runs",
        "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED','STALE')",
    )
    for column in (
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("fence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("event_seq", sa.Integer(), nullable=False, server_default="0"),
    ):
        op.add_column("investigation_runs", column)
    op.create_index(
        "ix_investigation_queue", "investigation_runs", ["status", "available_at", "lease_until"]
    )
    for table, extra, constraint in (
        (
            "investigation_events",
            [
                sa.Column("seq", sa.Integer(), nullable=False),
                sa.Column("event_type", sa.String(40), nullable=False),
                sa.Column("details", postgresql.JSONB(), nullable=False),
            ],
            sa.UniqueConstraint("run_id", "seq", name="uq_investigation_event_seq"),
        ),
        (
            "investigation_tool_results",
            [
                sa.Column("tool_name", sa.String(80), nullable=False),
                sa.Column("result", postgresql.JSONB(), nullable=False),
            ],
            sa.UniqueConstraint("run_id", "tool_name", name="uq_investigation_tool"),
        ),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("run_id", sa.Uuid(), sa.ForeignKey("investigation_runs.id"), nullable=False),
            *extra,
            constraint,
        )
        op.create_index(f"ix_{table}_run_id", table, ["run_id"])


def downgrade():
    # Explicit downgrade of queue metadata is allowed only when it will not destroy
    # unrepresentable active queue/cancellation state. Never coerce history silently.
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT count(*) FROM investigation_runs "
            "WHERE status IN ('QUEUED','RUNNING','CANCELLED')"
        )
    ):
        raise RuntimeError("Cannot downgrade while active/cancelled investigations exist")
    op.drop_table("investigation_tool_results")
    op.drop_table("investigation_events")
    op.drop_index("ix_investigation_queue", table_name="investigation_runs")
    for name in (
        "event_seq",
        "cancel_requested",
        "available_at",
        "attempts",
        "fence",
        "lease_until",
        "lease_owner",
    ):
        op.drop_column("investigation_runs", name)
    op.drop_constraint("investigation_status", "investigation_runs", type_="check")
    op.create_check_constraint(
        "investigation_status",
        "investigation_runs",
        "status IN ('RUNNING','COMPLETED','FAILED','STALE')",
    )
