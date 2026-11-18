import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.core.auth import require_operator
from app.modules.investigation.controls import control, events, list_runs
from app.modules.investigation.schemas import InvestigationRequest, InvestigationView
from app.modules.investigation.service import get_investigation, start_investigation
from app.modules.invoices.routes import Db, Operator

router = APIRouter(
    prefix="/api/v1", tags=["Investigations"], dependencies=[Depends(require_operator)]
)


@router.post(
    "/invoices/{invoice_id}/investigations", response_model=InvestigationView, status_code=202
)
def investigate(
    invoice_id: uuid.UUID,
    body: InvestigationRequest,
    session: Db,
    actor: Operator,
    response: Response,
):
    # Day 12 commits a snapshot-bound queue entry. HTTP never executes the graph.
    response.headers["Cache-Control"] = "no-store"
    return start_investigation(session, invoice_id, body, actor)


@router.get("/investigations/{run_id}", response_model=InvestigationView)
def investigation(run_id: uuid.UUID, session: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return get_investigation(session, run_id)


@router.get("/invoices/{invoice_id}/investigations")
def investigations(
    invoice_id: uuid.UUID,
    session: Db,
    response: Response,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    response.headers["Cache-Control"] = "no-store"
    return list_runs(session, invoice_id, limit, offset)


@router.get("/investigations/{run_id}/events")
def investigation_events(
    run_id: uuid.UUID,
    session: Db,
    response: Response,
    after_seq: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    return events(session, run_id, after_seq, limit)


@router.post("/investigations/{run_id}/cancel", response_model=InvestigationView)
def cancel_investigation(run_id: uuid.UUID, session: Db, actor: Operator, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return control(session, run_id, actor, "cancel")


@router.post("/investigations/{run_id}/retry", response_model=InvestigationView)
def retry_investigation(run_id: uuid.UUID, session: Db, actor: Operator, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return control(session, run_id, actor, "retry")
