from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.db.models import Decision
from app.modules.extraction.schemas import exact_decimal
from app.modules.validation.rules import normalize


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class RevisionRequest(StrictRequest):
    expected_revision: Annotated[int, Field(strict=True, ge=1, le=2147483647)]


class CorrectionRequest(RevisionRequest):
    changes: dict[str, Any] = Field(min_length=1, max_length=20)
    notes: str = Field(default="", max_length=2000)


class ReviewRequest(RevisionRequest):
    decision: Decision
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def rejection_needs_reason(self):
        self.notes = self.notes.strip()
        if self.decision == Decision.REJECT and not self.notes:
            raise ValueError("Rejection requires a reason")
        return self


class VendorCreate(StrictRequest):
    display_name: str = Field(min_length=1, max_length=200)
    expected_currency: Literal["USD", "EUR", "GBP", "JPY"] | None = None
    baseline_amount_limit: (
        Annotated[
            Decimal,
            BeforeValidator(exact_decimal),
            Field(ge=0, max_digits=18, decimal_places=2),
        ]
        | None
    ) = None
    is_approved: bool = Field(default=True, strict=True)

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value):
        if not normalize(value) or len(normalize(value)) > 200:
            raise ValueError("Invalid normalized supplier name")
        return value.strip()

    @field_validator("expected_currency", mode="before")
    @classmethod
    def currency_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def threshold_needs_currency(self):
        if self.baseline_amount_limit is not None and self.expected_currency is None:
            raise ValueError("An amount threshold requires an explicit currency")
        if (
            self.expected_currency == "JPY"
            and self.baseline_amount_limit is not None
            and self.baseline_amount_limit != self.baseline_amount_limit.to_integral_value()
        ):
            raise ValueError("JPY thresholds must be whole yen")
        return self
