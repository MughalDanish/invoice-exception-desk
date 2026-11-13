"""Generate deterministic synthetic invoices and a hash-indexed answer key (stdlib only)."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pdf_bytes(lines: list[str]) -> bytes:
    commands = ["BT /F1 12 Tf 40 800 Td"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -20 Td")
        commands.append(f"({escaped}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(result)


def main():
    base = {
        "vendor_name": "Alpha Office Supplies",
        "vendor_tax_id": None,
        "invoice_number": "INV-A-001",
        "invoice_date": "2026-11-13",
        "due_date": "2026-11-30",
        "currency": "USD",
        "line_items": [
            {
                "description": "Office paper",
                "quantity": "10",
                "unit_price": "100.00",
                "line_total": "1000.00",
            }
        ],
        "subtotal": "1000.00",
        "tax_rate": "0.15",
        "tax_amount": "150.00",
        "total": "1150.00",
        "evidence": {"invoice_number": "INV-A-001", "total": "USD 1150.00"},
        "uncertain_fields": [],
    }
    cases = []
    for index in range(1, 6):
        data = copy.deepcopy(base)
        data["invoice_number"] = f"INV-A-{index:03d}"
        cases.append((f"clean-{index:03d}.pdf", data, [], None))
    wrong_total = copy.deepcopy(base)
    wrong_total.update(
        vendor_name="Beta Tech",
        invoice_number="INV-B-002",
        subtotal="2000.00",
        tax_amount="300.00",
        total="2500.00",
    )
    wrong_total["line_items"][0].update(
        description="Software licenses", unit_price="200.00", line_total="2000.00"
    )
    cases.append(("wrong-total.pdf", wrong_total, ["TOTAL_MISMATCH"], None))
    wrong_line = copy.deepcopy(base)
    wrong_line["invoice_number"] = "INV-LINE-001"
    wrong_line["line_items"][0]["quantity"] = "9"
    cases.append(("wrong-line.pdf", wrong_line, ["LINE_TOTAL_MISMATCH"], None))
    wrong_tax = copy.deepcopy(base)
    wrong_tax.update(invoice_number="INV-TAX-001", tax_rate="0.10")
    cases.append(("wrong-tax.pdf", wrong_tax, ["TAX_RATE_MISMATCH"], None))
    cases.append(
        ("duplicate-copy.pdf", copy.deepcopy(base), ["DUPLICATE_FILE"], "clean-001.pdf")
    )
    cases.append(
        ("duplicate-resend.pdf", copy.deepcopy(base), ["DUPLICATE_INVOICE"], None)
    )
    altered = copy.deepcopy(base)
    altered.update(subtotal="2000.00", tax_amount="300.00", total="2300.00")
    altered["line_items"][0].update(unit_price="200.00", line_total="2000.00")
    cases.append(("duplicate-altered.pdf", altered, ["DUPLICATE_INVOICE"], None))
    for index in range(1, 3):
        data = copy.deepcopy(base)
        data.update(
            vendor_name=f"Unregistered Supplier {index}",
            invoice_number=f"INV-U-{index}",
        )
        cases.append((f"unknown-vendor-{index}.pdf", data, ["UNAPPROVED_VENDOR"], None))
    for field in ("invoice_number", "invoice_date"):
        data = copy.deepcopy(base)
        data.update(invoice_number=f"INV-MISSING-{field}")
        data[field] = None
        cases.append((f"missing-{field}.pdf", data, ["MISSING_REQUIRED_FIELD"], None))
    cases.append(("extraction-failure.pdf", None, ["EXTRACTION_FAILED"], None))
    output = ROOT / "fixtures" / "invoices"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "description": "Synthetic demo data; expected rules apply after extraction is built.",
        "fixtures": {},
    }
    for filename, payload, expected, duplicate_of in cases:
        if payload is not None:
            payload["evidence"] = {
                "invoice_number": payload["invoice_number"] or "",
                "total": "USD " + payload["total"],
            }
        if duplicate_of:
            content = (output / duplicate_of).read_bytes()
        else:
            lines = ["SYNTHETIC INVOICE - DEMONSTRATION ONLY", f"Fixture: {filename}"]
            if payload:
                for field in (
                    "vendor_name",
                    "invoice_number",
                    "invoice_date",
                    "due_date",
                    "currency",
                ):
                    if payload[field] is not None:
                        lines.append(f"{field}: {payload[field]}")
                for item in payload["line_items"]:
                    lines.append(
                        f"{item['description']}: {item['quantity']} x {item['unit_price']}"
                        f" = {item['line_total']}"
                    )
                for field in ("subtotal", "tax_rate", "tax_amount", "total"):
                    lines.append(f"{field}: {payload[field]}")
            else:
                lines.append(
                    "Unreadable supplier content: no extractable invoice facts"
                )
            content = pdf_bytes(lines)
        (output / filename).write_bytes(content)
        manifest["fixtures"][filename] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "extraction": payload,
            "expected_rule_codes": expected,
            "error_code": "MOCK_EXTRACTION_FAILED" if payload is None else None,
        }
    (ROOT / "fixtures" / "answers.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated {len(cases)} synthetic PDFs and fixtures/answers.json")


if __name__ == "__main__":
    main()
