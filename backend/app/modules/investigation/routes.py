import uuid

from fastapi import APIRouter, Depends, Response

from app.core.auth import require_operator
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
    # Day 6 finishes bounded local mock work synchronously, not a durable queued job.
    response.headers["Cache-Control"] = "no-store"
    return start_investigation(session, invoice_id, body, actor)


@router.get("/investigations/{run_id}", response_model=InvestigationView)
def investigation(run_id: uuid.UUID, session: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return get_investigation(session, run_id)
