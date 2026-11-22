"""Additive live migration round-trip and preservation guards in isolated schemas."""

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.models import InvestigationRun
from tests.conftest import ROOT
from tests.test_investigation import financial_state, prepared
from tests.test_investigation_durable import enqueue


def migrate(engine, target, *, upgrade):
    with engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        (command.upgrade if upgrade else command.downgrade)(config, target)


def test_live_migration_roundtrip_preserves_existing_financial_records(pg_client, pg_engine):
    prepared(pg_client, pg_engine)
    before = financial_state(pg_engine)
    added = {"requested_user_id", "requested_session_id", "budget_metadata"}
    migrate(pg_engine, "0009_durable_investigation", upgrade=False)
    assert not added & {
        column["name"] for column in inspect(pg_engine).get_columns("investigation_runs")
    }
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0009_durable_investigation"
        )
    migrate(pg_engine, "head", upgrade=True)
    assert added <= {
        column["name"] for column in inspect(pg_engine).get_columns("investigation_runs")
    }
    assert financial_state(pg_engine) == before


@pytest.mark.parametrize("live_mode", [True, False])
def test_downgrade_refuses_live_or_budget_history_without_mutation(pg_client, pg_engine, live_mode):
    identifier = prepared(pg_client, pg_engine)
    run_id, _ = enqueue(pg_client, identifier, "migration-preserve-history")
    with Session(pg_engine) as session, session.begin():
        row = session.get(InvestigationRun, run_id)
        row.mode = "gemini" if live_mode else "mock"
        row.budget_metadata = {} if live_mode else {"calls": [], "steps": 1}
        principal_before = (row.requested_user_id, row.requested_session_id)
    before = financial_state(pg_engine)
    with pytest.raises(RuntimeError, match="cannot be silently discarded"):
        migrate(pg_engine, "0009_durable_investigation", upgrade=False)
    with Session(pg_engine) as session:
        row = session.get(InvestigationRun, run_id)
        assert row.mode == ("gemini" if live_mode else "mock")
        assert row.budget_metadata == ({} if live_mode else {"calls": [], "steps": 1})
        assert (row.requested_user_id, row.requested_session_id) == principal_before
        assert (
            session.scalar(text("SELECT version_num FROM alembic_version"))
            == "0010_live_investigation"
        )
    assert financial_state(pg_engine) == before
