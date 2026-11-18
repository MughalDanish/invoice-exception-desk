"""Cycle-free, strict audit metadata for the bounded resolution review loop."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CriticCode = Literal[
    "UNSUPPORTED_CLAIM",
    "INVALID_CITATION",
    "SOURCE_BINDING",
    "UNSAFE_ACTION",
    "MISSING_EVIDENCE",
    "INVALID_OUTPUT",
    "CRITIC_REJECTED",
]


class CriticOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, hide_input_in_errors=True)
    accepted: bool
    codes: Annotated[tuple[CriticCode, ...], Field(max_length=7)] = ()


class ResolutionReview(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, hide_input_in_errors=True)
    accepted: bool
    escalated: bool
    attempts: Annotated[int, Field(ge=1, le=3)]
    codes: Annotated[tuple[CriticCode, ...], Field(max_length=7)] = ()
