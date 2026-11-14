"""Public read model: bundled synthetic data only, without DB or model access."""

import hashlib
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.db.models import InvoiceStatus
from app.modules.invoices.schemas import InvoiceDetail, VendorSummary
from app.modules.ledger.schemas import LedgerSummary

BUNDLED = Path(__file__).resolve().parents[3] / "fixtures"


def load_public_data():
    data = json.loads((BUNDLED / "public-demo.json").read_text(encoding="utf-8"))
    labels = json.loads((BUNDLED / "answers.json").read_text())["fixtures"]
    if data.get("synthetic") is not True or data.get("version") != 1:
        raise ValueError("Public demo requires a versioned synthetic export")
    for invoice in data["invoices"]:
        InvoiceDetail.model_validate(invoice)
        label = labels.get(invoice["filename"])
        if (
            not label
            or invoice["sha256"] != label["sha256"]
            or invoice["current_data"] != label["extraction"]
            or invoice["extracted_data"] != label["extraction"]
        ):
            raise ValueError("Public invoice must match bundled synthetic answer key")
        path = BUNDLED / "invoices" / invoice["filename"]
        if (
            path.parent.resolve() != (BUNDLED / "invoices").resolve()
            or hashlib.sha256(path.read_bytes()).hexdigest() != label["sha256"]
        ):
            raise ValueError("Bundled synthetic source hash mismatch")
    for row in data["vendors"]:
        VendorSummary.model_validate(row)
    for row in data["ledger"]:
        LedgerSummary.model_validate(row)
    return data


def create_public_router(data):
    router = APIRouter(prefix="/api/v1")
    records = {row["id"]: row for row in data["invoices"]}

    def invoice(invoice_id):
        row = records.get(str(invoice_id))
        if row is None:
            raise AppError(404, "INVOICE_NOT_FOUND", "Synthetic invoice not found")
        return row

    @router.get("/invoices")
    def invoices(
        status: InvoiceStatus | None = None,
        search: str = Query(default="", max_length=200),
        issue: str = Query(default="", max_length=80),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=25, ge=1, le=100),
    ):
        rows = []
        for row in records.values():
            payload = row["current_data"] or {}
            haystack = (
                " ".join(str(payload.get(key) or "") for key in ("vendor_name", "invoice_number"))
                + " "
                + row["filename"]
            )
            if (
                status
                and row["status"] != status.value
                or issue
                and issue not in row["issue_codes"]
                or search.casefold() not in haystack.casefold()
            ):
                continue
            rows.append(
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in (
                        "extracted_data",
                        "validations",
                        "processing_attempts",
                        "reviews",
                        "ledger_entry_id",
                    )
                }
            )
        return {
            "items": rows[(page - 1) * limit : page * limit],
            "total": len(rows),
            "page": page,
            "limit": limit,
        }

    @router.get("/invoices/{invoice_id}")
    def detail(invoice_id: uuid.UUID):
        return invoice(invoice_id)

    @router.get("/invoices/{invoice_id}/file")
    def source(invoice_id: uuid.UUID):
        row = invoice(invoice_id)
        return FileResponse(
            BUNDLED / "invoices" / row["filename"],
            media_type="application/pdf",
            filename=row["filename"],
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=300"},
        )

    @router.get("/invoices/{invoice_id}/audit")
    def audit(invoice_id: uuid.UUID):
        # Export only the finite synthetic audit read model. No arbitrary DB trace.
        invoice(invoice_id)
        return data["audits"].get(str(invoice_id), [])

    @router.get("/stats")
    def stats():
        return data["stats"]

    @router.get("/vendors")
    def vendors():
        return data["vendors"]

    @router.get("/ledger")
    def ledger(page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100)):
        return {
            "items": data["ledger"][(page - 1) * limit : page * limit],
            "total": len(data["ledger"]),
            "page": page,
            "limit": limit,
        }

    return router
