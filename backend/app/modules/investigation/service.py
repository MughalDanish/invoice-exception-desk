"""Own only investigation rows. Snapshot and publish in separate short transactions."""

import json
import re
import uuid
from datetime import UTC, datetime

from langsmith import tracing_context
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import InvestigationRun, Invoice, InvoiceStatus, Severity, ValidationResult
from app.modules.approvals.service import payload_hash
from app.modules.investigation.graph import build_graph
from app.modules.investigation.lookups import capture_lookups
from app.modules.investigation.providers import MockInvestigationProvider
from app.modules.investigation.schemas import (
    InvestigationReport,
    InvestigationRequest,
    InvestigationView,
    InvoiceSnapshot,
    RuleEvidence,
    exact_amount,
)


def locked_invoice(session, invoice_id):
    invoice = session.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
    return invoice


def snapshot_invoice(session, invoice) -> InvoiceSnapshot:
    if (
        invoice.status != InvoiceStatus.NEEDS_REVIEW
        or not invoice.current_data
        or not invoice.validation_run_id
    ):
        raise AppError(
            409,
            "INVESTIGATION_NOT_ELIGIBLE",
            "Investigation needs an extracted review invoice with current validation",
        )
    rules = session.scalars(
        select(ValidationResult)
        .where(
            ValidationResult.invoice_id == invoice.id,
            ValidationResult.revision == invoice.revision,
            ValidationResult.run_id == invoice.validation_run_id,
            ValidationResult.severity == Severity.BLOCKER,
            ValidationResult.passed.is_(False),
        )
        .order_by(ValidationResult.rule_code, ValidationResult.id)
        .limit(65)
    ).all()
    if not rules or len(rules) > 64:
        raise AppError(
            409, "INVESTIGATION_NOT_ELIGIBLE", "A bounded current blocker set is required"
        )
    currency = invoice.current_data.get("currency")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        currency = None
    return InvoiceSnapshot(
        invoice_id=invoice.id,
        revision=invoice.revision,
        payload_sha256=payload_hash(invoice.current_data),
        validation_batch_id=invoice.validation_run_id,
        document_sha256=invoice.sha256,
        lookup=capture_lookups(session, invoice),
        currency=currency,
        blockers=tuple(
            RuleEvidence(
                id=rule.id,
                code=rule.rule_code,
                expected_amount=exact_amount((rule.expected or {}).get("amount"))
                if isinstance(rule.expected, dict)
                else None,
                observed_amount=exact_amount((rule.observed or {}).get("amount"))
                if isinstance(rule.observed, dict)
                else None,
            )
            for rule in rules
        ),
    )


def matches(invoice, run, session) -> bool:
    return (
        invoice is not None
        and invoice.status == InvoiceStatus.NEEDS_REVIEW
        and invoice.revision == run.revision
        and invoice.validation_run_id == run.validation_batch_id
        and payload_hash(invoice.current_data) == run.payload_sha256
        and invoice.sha256 == run.snapshot["document_sha256"]
        and (
            "lookup" not in run.snapshot
            or run.snapshot["lookup"] is None
            or capture_lookups(session, invoice).model_dump(mode="json") == run.snapshot["lookup"]
        )
    )


def view(run, invoice, session) -> InvestigationView:
    current = matches(invoice, run, session)
    status = "STALE" if not current else run.status
    applicable = current and status == "COMPLETED"
    return InvestigationView(
        run_id=run.id,
        invoice_id=run.invoice_id,
        status=status,
        applicable=applicable,
        mode=run.mode,
        created_at=run.created_at,
        report=InvestigationReport.model_validate_json(json.dumps(run.report))
        if applicable and run.report
        else None,
        error_code=run.error_code,
    )


def start_investigation(session, invoice_id: uuid.UUID, body: InvestigationRequest, actor: str):
    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        existing = session.scalar(
            select(InvestigationRun).where(
                InvestigationRun.invoice_id == invoice_id,
                InvestigationRun.idempotency_key == body.idempotency_key,
            )
        )
        if existing:
            if existing.revision != body.expected_revision or not matches(
                invoice, existing, session
            ):
                raise AppError(
                    409,
                    "INVESTIGATION_KEY_CONFLICT",
                    "Request key belongs to a different invoice snapshot",
                )
            return view(existing, invoice, session)
        if invoice.revision != body.expected_revision:
            raise AppError(409, "STALE_REVISION", "Invoice changed; reload before investigation")
        snapshot = snapshot_invoice(session, invoice)
        run = InvestigationRun(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            revision=snapshot.revision,
            payload_sha256=snapshot.payload_sha256,
            validation_batch_id=snapshot.validation_batch_id,
            idempotency_key=body.idempotency_key,
            status="RUNNING",
            mode="mock",
            provider_version="scripted-supervisor-v2",
            policy_version="day-7-v1",
            requested_by=actor,
            snapshot=snapshot.model_dump(mode="json"),
        )
        session.add(run)
        session.flush()
        run_id = run.id
    # Only frozen data enters the graph. No session/ORM object or financial tools.
    report = None
    error_code = None
    try:
        # LangSmith is a transitive dependency, not consent to transmit traces.
        # Explicitly disable tracing even when the host exports tracing variables.
        with tracing_context(enabled=False):
            result = build_graph(MockInvestigationProvider()).invoke(
                {"run_id": run_id, "snapshot": snapshot, "findings": {}},
                config={"recursion_limit": 12, "callbacks": []},
            )
        report = InvestigationReport.model_validate(result["report"])
    except Exception:
        # Do not expose provider output or validation input through errors/logs.
        error_code = "INVESTIGATION_FAILED"
    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        run = session.get(InvestigationRun, run_id)
        run.finished_at = datetime.now(UTC)
        if not matches(invoice, run, session):
            run.status = "STALE"
        elif error_code:
            run.status = "FAILED"
            run.error_code = error_code
        else:
            run.status = "COMPLETED"
            run.report = report.model_dump(mode="json")
        session.flush()
        return view(run, invoice, session)


def get_investigation(session, run_id: uuid.UUID):
    run = session.get(InvestigationRun, run_id)
    if run is None:
        raise AppError(404, "INVESTIGATION_NOT_FOUND", "Investigation not found")
    # Fresh applicability on every read; immutable historical report stays in storage.
    return view(run, session.get(Invoice, run.invoice_id), session)
