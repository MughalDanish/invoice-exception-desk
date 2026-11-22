"""Standalone strict provenance types: no investigation dependency cycle."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceContract(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class Citation(EvidenceContract):
    source_id: UUID
    version: Annotated[int, Field(ge=1)]
    invoice_id: UUID
    supplier_key: Annotated[str, Field(min_length=1, max_length=200)]
    kind: Literal["PO", "RECEIPT", "EMAIL"]
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    excerpt: Annotated[str, Field(min_length=1, max_length=1000)]
    start: Annotated[int, Field(ge=0, le=999)] = 0
    end: Annotated[int, Field(ge=1, le=1000)]

    @property
    def citation_id(self) -> str:
        return f"source:{self.source_id}:v{self.version}:{self.content_sha256}"

    @property
    def href(self) -> str:
        return (
            f"/api/v1/invoices/{self.invoice_id}/evidence/{self.source_id}/versions/{self.version}"
        )

    @model_validator(mode="after")
    def exact_location(self):
        from app.modules.approvals.service import payload_hash

        # Documents are bounded to 1000 characters; keep the whole exact source
        # so the source hash can be verified without trusting a generated summary.
        if self.start != 0 or self.end != len(self.excerpt):
            raise ValueError("Invalid source location")
        if self.content_sha256 != payload_hash({"text": self.excerpt}):
            raise ValueError("Source integrity mismatch")
        return self


class RetrievalSnapshot(EvidenceContract):
    invoice_id: UUID
    supplier_key: Annotated[str, Field(max_length=200)]
    query: Annotated[str, Field(max_length=300)]
    exact_hits: Annotated[tuple[Citation, ...], Field(max_length=12)] = ()
    fts_hits: Annotated[tuple[Citation, ...], Field(max_length=12)] = ()
    hits: Annotated[tuple[Citation, ...], Field(max_length=12)] = ()
    truncated: bool = False
    algorithm: Literal["sql-fts-rrf-v1"] = "sql-fts-rrf-v1"
    rrf_k: Literal[60] = 60

    @model_validator(mode="after")
    def enforce_scope(self):
        for results in (self.exact_hits, self.fts_hits, self.hits):
            ids = set()
            for item in results:
                if (
                    item.invoice_id != self.invoice_id
                    or item.supplier_key != self.supplier_key
                    or item.source_id in ids
                ):
                    raise ValueError("Invalid retrieval scope or duplicate source")
                ids.add(item.source_id)
        captured = {c.citation_id: c for c in self.exact_hits + self.fts_hits}
        if any(captured.get(c.citation_id) != c for c in self.hits):
            raise ValueError("Fused citation absent from retrieval results")
        return self


def validate_citation(snapshot: RetrievalSnapshot, citation: Citation | str) -> bool:
    """Accept only exact captured citations, never a source ID invented by a model."""
    snapshot = RetrievalSnapshot.model_validate(snapshot)
    if isinstance(citation, str):
        return any(c.citation_id == citation for c in snapshot.hits)
    citation = Citation.model_validate(citation)
    return any(c == citation for c in snapshot.hits)
