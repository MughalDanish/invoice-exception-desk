"""Provider schema: fixed objects and string money, followed by strict local validation."""

from pydantic import BaseModel, Field


class GeminiLineItem(BaseModel):
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    line_total: str | None = None


class GeminiEvidence(BaseModel):
    invoice_number: str = ""
    total: str = ""
    vendor_name: str = ""
    invoice_date: str = ""


class GeminiInvoice(BaseModel):
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    line_items: list[GeminiLineItem] = Field(default_factory=list)
    subtotal: str | None = None
    tax_rate: str | None = None
    tax_amount: str | None = None
    total: str | None = None
    evidence: GeminiEvidence = Field(default_factory=GeminiEvidence)
    uncertain_fields: list[str] = Field(default_factory=list)
