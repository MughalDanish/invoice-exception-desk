"""Provider schema: fixed objects and string money, followed by strict local validation."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

DecimalText = Annotated[
    str,
    Field(
        max_length=80,
        description=(
            "Exact plain decimal string; no grouping commas, currency symbols "
            "or percent signs. Null if absent."
        ),
    ),
]


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class GeminiLineItem(ProviderModel):
    description: str | None = None
    quantity: DecimalText | None = None
    unit_price: DecimalText | None = None
    line_total: DecimalText | None = None


class GeminiEvidence(ProviderModel):
    invoice_number: str = ""
    total: str = ""
    vendor_name: str = ""
    invoice_date: str = ""


class GeminiInvoice(ProviderModel):
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    line_items: list[GeminiLineItem] = Field(default_factory=list)
    subtotal: DecimalText | None = None
    tax_rate: DecimalText | None = Field(
        default=None,
        description=(
            "Fractional tax rate. Explicit 5% becomes decimal string 0.05. "
            "Null when not printed; never infer from totals."
        ),
    )
    tax_amount: DecimalText | None = None
    total: DecimalText | None = None
    evidence: GeminiEvidence = Field(default_factory=GeminiEvidence)
    uncertain_fields: list[str] = Field(default_factory=list)
