import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.db.models import InvoiceStatus, Source


class InvoiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: Source
    filename: str
    mime_type: str
    sha256: str
    byte_size: int
    status: InvoiceStatus
    revision: int
    review_required: bool
    validation_run_id: uuid.UUID | None
    validated_revision: int | None
    vendor_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class InvoiceDetail(InvoiceSummary):
    extracted_data: dict | None
    current_data: dict | None
    validations: list[dict]
    processing_attempts: list[dict]
    reviews: list[dict]
    ledger_entry_id: uuid.UUID | None


class InvoiceActionResult(BaseModel):
    invoice_id: uuid.UUID
    status: InvoiceStatus
    revision: int
    review_required: bool
    validation_run_id: uuid.UUID | None
    validated_revision: int | None
    review_id: uuid.UUID | None = None


def action_result(invoice, review=None):
    return InvoiceActionResult(
        invoice_id=invoice.id,
        status=invoice.status,
        revision=invoice.revision,
        review_required=invoice.review_required,
        validation_run_id=invoice.validation_run_id,
        validated_revision=invoice.validated_revision,
        review_id=review.id if review else None,
    )


class ProcessingResult(BaseModel):
    invoice_id: uuid.UUID
    status: InvoiceStatus
    revision: int
    attempt_id: uuid.UUID | None
    error_code: str | None


class InvoicePage(BaseModel):
    items: list[InvoiceSummary]
    page: int
    limit: int
    total: int


class UploadResult(BaseModel):
    invoice_id: uuid.UUID
    status: InvoiceStatus
    duplicate: bool


class VendorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    expected_currency: str | None
    baseline_amount_limit: Decimal | None
    is_approved: bool


class AuditSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor: str
    event_type: str
    details: dict
    created_at: datetime
