import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.db.models import Decision, InvoiceReview, InvoiceStatus, Severity, Vendor
from app.modules.audit.service import record_event
from app.modules.extraction.adapters import ExtractionError, parse_extraction
from app.modules.extraction.processing import locked_invoice
from app.modules.extraction.schemas import InvoiceExtraction
from app.modules.invoices.states import transition
from app.modules.validation.rules import normalize
from app.modules.validation.service import identity, lock_identities, validate_current

EDITABLE = {InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.READY_TO_POST}


def payload_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def check_revision(invoice, expected):
    if invoice.revision != expected:
        raise AppError(
            409, "STALE_REVISION", "Invoice changed; reload before submitting this action"
        )


def require_editable(invoice):
    if invoice.status not in EDITABLE or invoice.current_data is None:
        raise AppError(
            409,
            "INVALID_INVOICE_STATE",
            "Only extracted, non-terminal invoices can be reviewed or corrected",
        )


def approval_for(session, invoice):
    return session.scalar(
        select(InvoiceReview).where(
            InvoiceReview.invoice_id == invoice.id,
            InvoiceReview.revision == invoice.revision,
            InvoiceReview.decision == Decision.APPROVE,
        )
    )


def approved_current(session, invoice):
    approval = approval_for(session, invoice)
    return approval is not None and approval.payload_sha256 == payload_hash(invoice.current_data)


def validate_for_action(session, invoice, settings, actor):
    try:
        data = parse_extraction(invoice.current_data)
        rules = validate_current(session, invoice, data, settings.money_tolerance, lock_vendor=True)
    except ExtractionError as exc:
        raise AppError(409, exc.code, "Current invoice data is not usable for validation") from exc
    blockers = [r.code for r in rules if not r.passed and r.severity == Severity.BLOCKER]
    if blockers:
        invoice.review_required = True
    record_event(
        session,
        actor,
        "VALIDATION_COMPLETED",
        invoice.id,
        {
            "revision": invoice.revision,
            "validation_run_id": str(invoice.validation_run_id),
            "blocker_codes": blockers,
        },
    )
    return data, blockers


def set_review_state(session, invoice, actor, blockers):
    target = (
        InvoiceStatus.NEEDS_REVIEW
        if blockers or (invoice.review_required and not approved_current(session, invoice))
        else InvoiceStatus.READY_TO_POST
    )
    if invoice.status != target:
        transition(session, invoice, target, actor)


def correct_invoice(session, invoice_id, body, actor):
    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        check_revision(invoice, body.expected_revision)
        require_editable(invoice)
        if set(body.changes) - InvoiceExtraction.model_fields.keys():
            raise AppError(
                422, "INVALID_CORRECTION", "Only extracted invoice fields can be corrected"
            )
        before = invoice.current_data
        try:
            data = parse_extraction({**before, **body.changes})
            vendor_name, number = identity(data)
        except ExtractionError as exc:
            raise AppError(
                422, "INVALID_CORRECTION", "Corrected fields do not match the extraction schema"
            ) from exc
        after = data.model_dump(mode="json")
        diff = {
            key: {"before": before.get(key), "after": after.get(key)}
            for key in after
            if before.get(key) != after.get(key)
        }
        if not diff:
            record_event(
                session,
                actor,
                "CORRECTION_NO_CHANGE",
                invoice.id,
                {"revision": invoice.revision, "notes": body.notes},
            )
            return invoice
        if invoice.revision == 2147483647:
            raise AppError(409, "REVISION_LIMIT", "Invoice revision limit reached")
        lock_identities(
            session,
            (invoice.normalized_vendor_name, invoice.normalized_invoice_number),
            (vendor_name, number),
        )
        vendor = session.scalar(select(Vendor).where(Vendor.normalized_name == vendor_name))
        old_revision = invoice.revision
        invoice.current_data = after
        invoice.revision += 1
        invoice.validation_run_id = None
        invoice.review_required = True
        invoice.normalized_vendor_name = vendor_name or None
        invoice.normalized_invoice_number = number or None
        invoice.vendor_id = vendor.id if vendor else None
        transition(session, invoice, InvoiceStatus.NEEDS_REVIEW, actor, {"reason": "CORRECTION"})
        record_event(
            session,
            actor,
            "INVOICE_CORRECTED",
            invoice.id,
            {
                "from_revision": old_revision,
                "revision": invoice.revision,
                "diff": diff,
                "notes": body.notes,
            },
        )
    return invoice


def revalidate_invoice(session, invoice_id, body, settings, actor):
    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        check_revision(invoice, body.expected_revision)
        require_editable(invoice)
        _, blockers = validate_for_action(session, invoice, settings, actor)
        set_review_state(session, invoice, actor, blockers)
    return invoice


def review_invoice(session, invoice_id, body, settings, actor):
    failure = None
    with session.begin():
        invoice = locked_invoice(session, invoice_id)
        check_revision(invoice, body.expected_revision)
        existing = session.scalar(
            select(InvoiceReview).where(
                InvoiceReview.invoice_id == invoice.id,
                InvoiceReview.revision == invoice.revision,
                InvoiceReview.decision == body.decision,
            )
        )
        if existing and existing.notes != body.notes:
            raise AppError(
                409,
                "REVIEW_ALREADY_RECORDED",
                "Review notes are immutable; this decision is already recorded",
            )
        if (
            invoice.status == InvoiceStatus.REJECTED
            and existing
            and body.decision == Decision.REJECT
        ):
            return invoice, existing
        require_editable(invoice)
        if body.decision == Decision.REJECT:
            invoice.review_required = True
            if invoice.status == InvoiceStatus.READY_TO_POST:
                transition(
                    session,
                    invoice,
                    InvoiceStatus.NEEDS_REVIEW,
                    actor,
                    {"reason": "OPERATOR_REJECTION_REQUESTED"},
                )
            review = InvoiceReview(
                invoice_id=invoice.id,
                revision=invoice.revision,
                decision=body.decision,
                notes=body.notes,
                reviewer=actor,
                payload_sha256=payload_hash(invoice.current_data),
            )
            session.add(review)
            transition(session, invoice, InvoiceStatus.REJECTED, actor)
            record_event(
                session,
                actor,
                "INVOICE_REJECTED",
                invoice.id,
                {"revision": invoice.revision, "notes": body.notes},
            )
        else:
            if invoice.validation_run_id is None:
                raise AppError(
                    409, "REVALIDATION_REQUIRED", "Revalidate the current revision before approving"
                )
            _, blockers = validate_for_action(session, invoice, settings, actor)
            if blockers:
                set_review_state(session, invoice, actor, blockers)
                record_event(
                    session,
                    actor,
                    "APPROVAL_BLOCKED",
                    invoice.id,
                    {"revision": invoice.revision, "blocker_codes": blockers},
                )
                failure = AppError(
                    409, "VALIDATION_BLOCKED", "Blocking rules: " + ", ".join(blockers)
                )
                review = None
            elif existing and existing.payload_sha256 != payload_hash(invoice.current_data):
                raise AppError(
                    409,
                    "REVIEW_PAYLOAD_CHANGED",
                    "Payload differs from the recorded review; create a corrected revision",
                )
            else:
                review = existing
                if review is None:
                    review = InvoiceReview(
                        invoice_id=invoice.id,
                        revision=invoice.revision,
                        decision=body.decision,
                        notes=body.notes,
                        reviewer=actor,
                        payload_sha256=payload_hash(invoice.current_data),
                    )
                    session.add(review)
                    session.flush()
                    record_event(
                        session,
                        actor,
                        "INVOICE_APPROVED",
                        invoice.id,
                        {
                            "revision": invoice.revision,
                            "review_id": str(review.id),
                            "payload_sha256": review.payload_sha256,
                            "notes": body.notes,
                        },
                    )
                set_review_state(session, invoice, actor, [])
    if failure:
        raise failure
    return invoice, review


def create_vendor(session, body, actor):
    try:
        with session.begin():
            vendor = Vendor(**body.model_dump(), normalized_name=normalize(body.display_name))
            session.add(vendor)
            session.flush()
            record_event(
                session,
                actor,
                "VENDOR_CREATED",
                details={
                    "vendor_id": str(vendor.id),
                    "display_name": vendor.display_name,
                    "expected_currency": vendor.expected_currency,
                    "baseline_amount_limit": str(vendor.baseline_amount_limit)
                    if vendor.baseline_amount_limit is not None
                    else None,
                    "is_approved": vendor.is_approved,
                },
            )
        return vendor
    except IntegrityError as exc:
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "uq_vendors_normalized_name"
        ):
            raise AppError(
                409, "VENDOR_EXISTS", "A supplier with this normalized name already exists"
            ) from exc
        raise
