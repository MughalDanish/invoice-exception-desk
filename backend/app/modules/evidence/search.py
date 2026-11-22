"""Exact SQL + PostgreSQL FTS with deterministic reciprocal rank fusion."""

import re
from fractions import Fraction

from sqlalchemy import text

from app.modules.evidence.schemas import Citation, RetrievalSnapshot

# Both scopes and latest-version selection precede either relevance filter.
LATEST = """
WITH scoped AS MATERIALIZED (
 SELECT DISTINCT ON (source_id) * FROM investigation_documents
 WHERE invoice_id = :invoice_id AND supplier_key = :supplier_key
 ORDER BY source_id, version DESC
)
"""


def citation_from_row(row) -> Citation:
    return Citation(
        source_id=row.source_id,
        version=row.version,
        invoice_id=row.invoice_id,
        supplier_key=row.supplier_key,
        kind=row.kind,
        content_sha256=row.content_sha256,
        excerpt=row.content,
        end=len(row.content),
    )


def reciprocal_rank_fusion(*rankings, limit=12):
    scores, sources = {}, {}
    for ranking in rankings:
        for rank, citation in enumerate(ranking, 1):
            key = citation.citation_id
            scores[key] = scores.get(key, Fraction(0)) + Fraction(1, 60 + rank)
            if key in sources and sources[key] != citation:
                raise ValueError("Conflicting source citation")
            sources[key] = citation
    return tuple(sources[key] for key in sorted(scores, key=lambda k: (-scores[k], k))[:limit])


def retrieve(session, invoice, query: str) -> RetrievalSnapshot:
    """Internal bounded search. API callers cannot provide supplier or SQL scope."""
    supplier = invoice.normalized_vendor_name or ""
    # No operators, URLs, SQL or arbitrary model-controlled query grammar.
    candidates = list(dict.fromkeys(re.findall(r"[a-z0-9]{1,40}", query.lower())))[:20]
    tokens = []
    for token in candidates:
        if len(" ".join((*tokens, token))) > 300:
            break
        tokens.append(token)
    query = " ".join(tokens)
    empty = RetrievalSnapshot(invoice_id=invoice.id, supplier_key=supplier, query=query)
    if not supplier:
        return empty
    params = {
        "invoice_id": invoice.id,
        "supplier_key": supplier,
        "identity": invoice.normalized_invoice_number or "",
        "query": " | ".join(tokens),
    }
    exact_rows = session.execute(
        text(
            LATEST
            + """
 SELECT * FROM scoped
 WHERE :identity <> '' AND strpos(lower(content), :identity) > 0
 ORDER BY source_id LIMIT 13
 """
        ),
        params,
    ).all()
    fts_rows = []
    if tokens:
        fts_rows = session.execute(
            text(
                LATEST
                + """
 SELECT * FROM scoped
 WHERE to_tsvector('english', content) @@ to_tsquery('english', :query)
 ORDER BY ts_rank_cd(to_tsvector('english', content),
                     to_tsquery('english', :query)) DESC, source_id
 LIMIT 13
 """
            ),
            params,
        ).all()
    exact = tuple(citation_from_row(r) for r in exact_rows[:12])
    fts = tuple(citation_from_row(r) for r in fts_rows[:12])
    return RetrievalSnapshot(
        invoice_id=invoice.id,
        supplier_key=supplier,
        query=query,
        exact_hits=exact,
        fts_hits=fts,
        hits=reciprocal_rank_fusion(exact, fts),
        truncated=len(exact_rows) > 12 or len(fts_rows) > 12,
    )


def capture_retrieval(session, invoice) -> RetrievalSnapshot:
    # Fixed vocabulary is versioned by algorithm, never supplied by document text.
    query = (
        invoice.normalized_invoice_number or ""
    ) + " purchase receipt delivery amendment supplier discrepancy"
    return retrieve(session, invoice, query)
