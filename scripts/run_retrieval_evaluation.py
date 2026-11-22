"""Annotated synthetic recall@5 comparison using real PostgreSQL SQL/FTS/RRF."""

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import InvestigationDocument, Invoice
from app.modules.approvals.service import payload_hash
from app.modules.evidence.search import retrieve
from app.qa import isolated_client, process, upload
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def evaluate(url):
    corpus = json.loads(
        (ROOT / "fixtures/investigation/retrieval-cases.json").read_text()
    )
    cases = []
    vector_available = False
    for case in corpus["cases"]:
        with isolated_client(url) as client:
            identifier = uuid.UUID(upload(client, "wrong-total.pdf")["invoice_id"])
            process(client, str(identifier))
            with Session(client.app.state.engine) as db:
                vector_available = bool(
                    db.scalar(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name='vector')"
                        )
                    )
                )
                invoice = db.get(Invoice, identifier)
                relevant = set()
                for document in case["documents"]:
                    source_id = uuid.uuid5(
                        uuid.NAMESPACE_URL, case["name"] + document["key"]
                    )
                    content = document["text"].replace(
                        "{invoice}", invoice.normalized_invoice_number
                    )
                    db.add(
                        InvestigationDocument(
                            source_id=source_id,
                            version=1,
                            invoice_id=identifier,
                            supplier_key=invoice.normalized_vendor_name,
                            kind=document["kind"],
                            content=content,
                            content_sha256=payload_hash({"text": content}),
                        )
                    )
                    if document["relevant"]:
                        relevant.add(source_id)
                db.commit()
                captured = retrieve(db, invoice, case["query"])
                metrics = {}
                for name, hits in (
                    ("exact_sql", captured.exact_hits),
                    ("fts", captured.fts_hits),
                    ("rrf", captured.hits),
                ):
                    found = {c.source_id for c in hits[:5]}
                    metrics[name] = {
                        "relevant_found": len(found & relevant),
                        "relevant_total": len(relevant),
                        "recall_at_5": len(found & relevant) / len(relevant),
                    }
                cases.append({"case": case["name"], "metrics": metrics})
    means = {
        name: sum(c["metrics"][name]["recall_at_5"] for c in cases) / len(cases)
        for name in ("exact_sql", "fts", "rrf")
    }
    return {
        "synthetic": True,
        "split": "development diagnostic",
        "cases": cases,
        "macro_recall_at_5": means,
        "pgvector_available": vector_available,
        "pgvector_used": False,
        "live_model_quality": "NOT RUN",
    }


def main():
    values = dotenv_values(ROOT / ".env")
    url = make_url(os.getenv("TEST_DATABASE_URL") or values["DATABASE_URL"])
    if url.host == "postgres":
        url = url.set(host="127.0.0.1", port=5433)
    result = evaluate(url)
    output = ROOT / "storage/day-9-retrieval-evaluation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("All synthetic schemas removed; no live invoices or financial writes.")


if __name__ == "__main__":
    main()
