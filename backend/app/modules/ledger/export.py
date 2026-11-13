import csv
import io
import unicodedata

from app.modules.ledger.schemas import ledger_summary

CSV_FIELDS = [
    "ledger_id",
    "invoice_id",
    "vendor",
    "invoice_number",
    "invoice_date",
    "revision",
    "currency",
    "total",
    "posted_at",
    "posted_by",
]


def safe_cell(value):
    text = "" if value is None else str(value)
    probe = unicodedata.normalize("NFKC", text)
    offset = 0
    while offset < len(probe) and (probe[offset].isspace() or probe[offset] in "\ufeff\u200b"):
        offset += 1
    probe = probe[offset:]
    if probe.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(CSV_FIELDS)
    for entry, vendor_name in rows:
        row = ledger_summary(entry, vendor_name)
        writer.writerow(
            [
                safe_cell(value)
                for value in (
                    row.id,
                    row.invoice_id,
                    row.vendor_name,
                    row.invoice_number,
                    row.invoice_date,
                    row.invoice_revision,
                    row.currency,
                    f"{row.total:.2f}",
                    row.posted_at.isoformat(),
                    row.posted_by,
                )
            ]
        )
    return output.getvalue().encode("utf-8-sig")
