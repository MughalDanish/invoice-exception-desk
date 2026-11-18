"""Own only investigation rows. Snapshot and publish in separate short transactions."""

import json
import re
import uuid

from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import InvestigationRun, Invoice, InvoiceStatus, Severity, ValidationResult
from app.modules.approvals.service import payload_hash
from app.modules.evidence.search import capture_retrieval
from app.modules.investigation.documents import capture_documents
from app.modules.investigation.lookups import capture_lookups
from app.modules.investigation.queue import event
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
        documents=capture_documents(session, invoice),
        retrieval=capture_retrieval(session, invoice),
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
            run.snapshot.get("retrieval") is None
            or capture_retrieval(session, invoice).model_dump(mode="json")
            == run.snapshot["retrieval"]
        )
        and (
            run.snapshot.get("documents") is None
            or capture_documents(session, invoice).model_dump(mode="json")
            == run.snapshot["documents"]
        )
        and (
            "lookup" not in run.snapshot
            or run.snapshot["lookup"] is None
            or capture_lookups(session, invoice).model_dump(mode="json") == run.snapshot["lookup"]
        )
    )


def view(run, invoice, session) -> InvestigationView:
    current = matches(invoice, run, session)
    status = "STALE" if not current and run.status != "CANCELLED" else run.status
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
        execution="durable_worker"
        if run.provider_version == "scripted-durable-v4"
        else "synchronous_local",
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
            status="QUEUED",
            mode="mock",
            provider_version="scripted-durable-v4",
            policy_version="days-9-12-v1",
            requested_by=actor,
            snapshot=snapshot.model_dump(mode="json"),
        )
        session.add(run)
        session.flush()
        event(session, run, "QUEUED")
        session.flush()
        return view(run, invoice, session)


def get_investigation(session, run_id: uuid.UUID):
    run = session.get(InvestigationRun, run_id)
    if run is None:
        raise AppError(404, "INVESTIGATION_NOT_FOUND", "Investigation not found")
    # Fresh applicability on every read; immutable historical report stays in storage.
    return view(run, session.get(Invoice, run.invoice_id), session)
