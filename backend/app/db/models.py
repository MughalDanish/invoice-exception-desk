import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceStatus(enum.StrEnum):
    RECEIVED = "RECEIVED"
    EXTRACTING = "EXTRACTING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY_TO_POST = "READY_TO_POST"
    POSTED = "POSTED"
    REJECTED = "REJECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class Source(enum.StrEnum):
    api = "api"
    gmail = "gmail"
    fixture = "fixture"


class Severity(enum.StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"


class Decision(enum.StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class AttemptStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def enum_type(cls):
    return Enum(cls, name=cls.__name__.lower(), native_enum=False, create_constraint=True)


class IdentityMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vendor(IdentityMixin, Base):
    __tablename__ = "vendors"

    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    expected_currency: Mapped[str | None] = mapped_column(String(3))
    baseline_amount_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class Invoice(IdentityMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_invoices_sha256"),
        Index(
            "uq_invoices_source_delivery",
            "source",
            "source_message_id",
            "sha256",
            unique=True,
            postgresql_where=text("source_message_id IS NOT NULL"),
        ),
        CheckConstraint("revision >= 1", name="positive_revision"),
        CheckConstraint("byte_size > 0", name="positive_size"),
        Index("ix_invoices_status_created_at", "status", "created_at"),
        Index(
            "ix_invoices_business_identity", "normalized_vendor_name", "normalized_invoice_number"
        ),
    )

    source: Mapped[Source] = mapped_column(enum_type(Source))
    source_message_id: Mapped[str | None] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(50))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(255))
    status: Mapped[InvoiceStatus] = mapped_column(
        enum_type(InvoiceStatus), default=InvoiceStatus.RECEIVED
    )
    extracted_data: Mapped[dict | None] = mapped_column(JSONB)
    current_data: Mapped[dict | None] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    normalized_vendor_name: Mapped[str | None] = mapped_column(String(200))
    normalized_invoice_number: Mapped[str | None] = mapped_column(String(200))
    review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    validation_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def validated_revision(self):
        return self.revision if self.validation_run_id else None


class ValidationResult(IdentityMixin, Base):
    __tablename__ = "validation_results"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    rule_code: Mapped[str] = mapped_column(String(80))
    severity: Mapped[Severity] = mapped_column(enum_type(Severity))
    passed: Mapped[bool] = mapped_column(Boolean)
    message: Mapped[str] = mapped_column(Text)
    expected: Mapped[dict | None] = mapped_column(JSONB)
    observed: Mapped[dict | None] = mapped_column(JSONB)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)


class IntegrationDelivery(IdentityMixin, Base):
    __tablename__ = "integration_deliveries"

    key_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    file_sha256: Mapped[str] = mapped_column(String(64))
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)


class InvoiceReview(IdentityMixin, Base):
    __tablename__ = "invoice_reviews"
    __table_args__ = (UniqueConstraint("invoice_id", "revision", "decision"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    reviewer: Mapped[str] = mapped_column(String(200))
    decision: Mapped[Decision] = mapped_column(enum_type(Decision))
    notes: Mapped[str] = mapped_column(Text, default="")
    payload_sha256: Mapped[str | None] = mapped_column(String(64))


class LedgerEntry(IdentityMixin, Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("vendor_id", "invoice_number_normalized", name="uq_ledger_vendor_number"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), unique=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"))
    invoice_number_normalized: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    posted_by: Mapped[str] = mapped_column(String(200))
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class AuditEvent(IdentityMixin, Base):
    __tablename__ = "audit_events"

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    actor: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class ProcessingAttempt(IdentityMixin, Base):
    __tablename__ = "processing_attempts"
    __table_args__ = (
        UniqueConstraint("invoice_id", "ordinal"),
        CheckConstraint("ordinal >= 1", name="positive_ordinal"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(enum_type(AttemptStatus))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class AuthUser(IdentityMixin, Base):
    __tablename__ = "auth_users"
    username: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="OPERATOR", server_default="OPERATOR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class AuthSession(IdentityMixin, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth_users.id"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(40))


class AuthLoginWindow(Base):
    __tablename__ = "auth_login_windows"
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer)


class InvestigationRun(IdentityMixin, Base):
    __tablename__ = "investigation_runs"
    __table_args__ = (
        UniqueConstraint("invoice_id", "idempotency_key", name="uq_investigation_request"),
        CheckConstraint("revision >= 1", name="investigation_positive_revision"),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'STALE')",
            name="investigation_status",
        ),
        CheckConstraint("mode IN ('mock','gemini')", name="investigation_mock_only"),
        Index("ix_investigation_invoice_created", "invoice_id", "created_at"),
        Index("ix_investigation_queue", "status", "available_at", "lease_until"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    revision: Mapped[int] = mapped_column(Integer)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    validation_batch_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))
    provider_version: Mapped[str] = mapped_column(String(80))
    policy_version: Mapped[str] = mapped_column(String(40))
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    requested_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    budget_metadata: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    snapshot: Mapped[dict] = mapped_column(JSONB)
    report: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    event_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class InvestigationEvent(IdentityMixin, Base):
    __tablename__ = "investigation_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_investigation_event_seq"),)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigation_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class InvestigationToolResult(IdentityMixin, Base):
    __tablename__ = "investigation_tool_results"
    __table_args__ = (UniqueConstraint("run_id", "tool_name", name="uq_investigation_tool"),)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigation_runs.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    result: Mapped[dict] = mapped_column(JSONB)


class InvestigationDocument(Base):
    """Versioned, append-only supporting evidence. No financial authority."""

    __tablename__ = "investigation_documents"
    __table_args__ = (
        CheckConstraint("version >= 1", name="evidence_positive_version"),
        CheckConstraint("kind IN ('PO', 'RECEIPT', 'EMAIL')", name="evidence_kind"),
        CheckConstraint("length(content) BETWEEN 1 AND 1000", name="evidence_size"),
        Index("ix_evidence_scope", "invoice_id", "supplier_key", "source_id", "version"),
        Index(
            "ix_evidence_fts",
            text("to_tsvector('english'::regconfig, content)"),
            postgresql_using="gin",
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    supplier_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
