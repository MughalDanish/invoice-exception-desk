from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def exact_decimal(value):
    if isinstance(value, (float, bool)):
        raise ValueError("Financial values must be decimal strings, not binary floats")
    return value


Number = Annotated[
    Decimal,
    BeforeValidator(exact_decimal),
    Field(allow_inf_nan=False, max_digits=24, decimal_places=6),
]
Text = Annotated[str, Field(max_length=200)]


class LineItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, revalidate_instances="always"
    )

    description: Text | None = None
    quantity: Number | None = None
    unit_price: Number | None = None
    line_total: Number | None = None


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, revalidate_instances="always"
    )

    vendor_name: Text | None = None
    vendor_tax_id: Text | None = None
    invoice_number: Text | None = None
    # Preserve invalid date text so the rule engine can route it for correction.
    invoice_date: Annotated[str, Field(max_length=40)] | None = None
    due_date: Annotated[str, Field(max_length=40)] | None = None
    currency: Annotated[str, Field(max_length=10)] | None = None
    line_items: list[LineItem] = Field(default_factory=list, max_length=500)
    subtotal: Number | None = None
    tax_rate: Number | None = None
    tax_amount: Number | None = None
    total: Number | None = None
    evidence: dict[Text, Annotated[str, Field(max_length=500)]] = Field(default_factory=dict)
    uncertain_fields: list[Text] = Field(default_factory=list, max_length=100)
