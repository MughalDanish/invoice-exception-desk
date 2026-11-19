"""Short queue transactions. Events contain IDs/status, never evidence text or prompts."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from app.db.models import InvestigationEvent, InvestigationRun

MAX_ATTEMPTS = 3


def database_now(session):
    return session.scalar(select(func.clock_timestamp()))


def event(session, run, event_type, **details):
    # Caller holds the run row lock; sequence is monotonic across workers and API controls.
    run.event_seq += 1
    session.add(
        InvestigationEvent(run_id=run.id, seq=run.event_seq, event_type=event_type, details=details)
    )


@dataclass(frozen=True)
class Claim:
    run_id: uuid.UUID
    owner: str
    fence: int


def claim_next(factory, owner, *, lease_seconds=30, run_id=None):
    with factory.begin() as session:
        now = database_now(session)
        query = select(InvestigationRun).where(
            InvestigationRun.provider_version.in_(("scripted-durable-v4", "gemini-mcp-v1")),
            InvestigationRun.cancel_requested.is_(False),
            or_(
                and_(InvestigationRun.status == "QUEUED", InvestigationRun.available_at <= now),
                and_(InvestigationRun.status == "RUNNING", InvestigationRun.lease_until <= now),
            ),
        )
        if run_id is not None:
            query = query.where(InvestigationRun.id == run_id)
        run = session.scalar(
            query.order_by(InvestigationRun.created_at, InvestigationRun.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if run is None:
            return None
        if run.attempts >= MAX_ATTEMPTS:
            run.status, run.error_code = "FAILED", "INVESTIGATION_RETRIES_EXHAUSTED"
            run.finished_at, run.fence = now, run.fence + 1
            run.lease_owner = run.lease_until = None
            event(session, run, "RETRIES_EXHAUSTED")
            return None
        run.status, run.lease_owner = "RUNNING", owner
        run.fence += 1
        run.attempts += 1
        run.lease_until = now + timedelta(seconds=lease_seconds)
        event(session, run, "CLAIMED", attempt=run.attempts, generation=run.fence)
        return Claim(run.id, owner, run.fence)


def owned(run, claim, now):
    return bool(
        run
        and run.status == "RUNNING"
        and not run.cancel_requested
        and run.lease_owner == claim.owner
        and run.fence == claim.fence
        and run.lease_until
        and run.lease_until > now
    )


def heartbeat(factory, claim, lease_seconds):
    with factory.begin() as session:
        run = session.scalar(
            select(InvestigationRun).where(InvestigationRun.id == claim.run_id).with_for_update()
        )
        now = database_now(session)
        if not owned(run, claim, now):
            return False
        run.lease_until = now + timedelta(seconds=lease_seconds)
        return True
