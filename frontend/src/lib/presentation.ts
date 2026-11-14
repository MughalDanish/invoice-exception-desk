import type { Event, Rule } from "./api";

export function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export const text = (value: unknown, fallback = "Not provided"): string =>
  typeof value === "string" && value.trim() ? value : fallback;

// Group the integer substring only: no Number/parseFloat, rounding, padding or FX.
export function decimal(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "Not provided";
  if (!/^[+-]?\d+(?:\.\d+)?$/.test(value)) return value;
  const [integer, fraction] = value.split(".");
  return (
    integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") +
    (fraction === undefined ? "" : `.${fraction}`)
  );
}
export function financial(value: unknown, currency: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "Not provided";
  return `${text(currency, "Currency not provided")} ${decimal(value)}`;
}
export function timestamp(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "Time not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Time not recorded"
    : new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      }).format(date);
}
const labels: Record<string, string> = {
  vendor_name: "Supplier",
  vendor_tax_id: "Supplier tax ID",
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  due_date: "Due date",
  currency: "Currency",
  subtotal: "Subtotal",
  tax_rate: "Tax rate (fraction)",
  tax_amount: "Tax amount",
  total: "Total",
  line_items: "Line items",
  description: "Description",
  quantity: "Quantity",
  unit_price: "Unit price",
  line_total: "Line total",
  evidence: "Source evidence",
  uncertain_fields: "Uncertain fields",
  fields: "Fields",
  missing: "Missing fields",
  invalid_fields: "Invalid fields",
  currencies: "Supported currencies",
  amount: "Amount",
  mismatches: "Line discrepancies",
  line: "Line",
  expected: "Expected",
  observed: "Observed",
};
export const fieldLabel = (key: string): string =>
  labels[key] || key.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
export const monetaryField = (key: string): boolean =>
  [
    "subtotal",
    "tax_amount",
    "total",
    "unit_price",
    "line_total",
    "amount",
  ].includes(key);
const ruleLabels: Record<string, string> = {
  MISSING_REQUIRED_FIELD: "Required invoice information",
  INVALID_DATE: "Invoice dates",
  INVALID_DATE_RANGE: "Invoice date range",
  UNSUPPORTED_CURRENCY: "Supported currency",
  MONEY_PRECISION: "Currency precision",
  AMOUNT_RANGE: "Supported amount range",
  NEGATIVE_AMOUNT: "Non-negative amounts",
  INVALID_TAX_RATE: "Tax rate range",
  ARITHMETIC_INCOMPLETE: "Arithmetic information",
  LINE_TOTAL_MISMATCH: "Line-item arithmetic",
  SUBTOTAL_MISMATCH: "Invoice subtotal",
  TOTAL_MISMATCH: "Invoice total",
  TAX_RATE_MISMATCH: "Tax calculation",
  UNAPPROVED_VENDOR: "Supplier approval",
  DUPLICATE_INVOICE: "Duplicate invoice identity",
  DUPLICATE_FILE: "Duplicate source document",
  CURRENCY_MISMATCH: "Supplier currency policy",
  AMOUNT_OUTLIER: "Supplier review threshold",
  UNCERTAIN_EXTRACTION: "Extraction evidence",
};
export const ruleLabel = (code: string): string =>
  ruleLabels[code] || "Additional validation check";
export function outcome(rule: Rule): string {
  if (rule.passed) return "Passed";
  if (rule.severity === "BLOCKER") return "Blocks posting";
  if (rule.severity === "WARNING") return "Warning";
  return "Failed check";
}
export function validationGroups(rules: readonly Rule[]) {
  const rank = (r: Rule) =>
    r.severity === "BLOCKER" ? 0 : r.severity === "WARNING" ? 1 : 2;
  return {
    failed: rules.filter((r) => !r.passed).sort((a, b) => rank(a) - rank(b)),
    passed: rules.filter((r) => r.passed),
    blocking: rules.filter((r) => !r.passed && r.severity === "BLOCKER").length,
    warnings: rules.filter((r) => !r.passed && r.severity === "WARNING").length,
  };
}
const guidance: Record<string, string> = {
  TOTAL_MISMATCH:
    "Compare subtotal, tax and total with the source. Correct an extraction error or obtain a corrected invoice; do not substitute the expected amount automatically.",
  SUBTOTAL_MISMATCH:
    "Compare the source line totals with the subtotal before correcting any field.",
  LINE_TOTAL_MISMATCH:
    "Check the quantity, unit price and line total against each affected source line.",
  TAX_RATE_MISMATCH:
    "Verify the explicit tax rate and source tax amount; do not infer a rate from a jurisdiction.",
  DUPLICATE_INVOICE:
    "Review the supplier and invoice number against existing invoices. A changed amount does not clear a duplicate; reject only after checking the evidence.",
  UNAPPROVED_VENDOR:
    "Check the supplier registry. An authorized supplier registration must be followed by invoice revalidation; approval cannot bypass this check.",
  INVALID_DATE_RANGE:
    "Verify both source dates. The due date must not precede the invoice date.",
  MISSING_REQUIRED_FIELD:
    "Find the missing information in the source. Leave unknown values missing rather than guessing.",
  UNCERTAIN_EXTRACTION:
    "Compare uncertain fields and evidence snippets with the original document before resolving them.",
};
export const ruleGuidance = (code: string): string =>
  guidance[code] ||
  "Review the source and recorded evidence, correct only verified information, then revalidate. A blocking result cannot be waived by approval.";

export type AuditView = {
  title: string;
  description: string;
  icon: "document" | "arrow" | "check" | "edit" | "stop" | "ledger" | "info";
  tone: "neutral" | "good" | "warning";
  notes?: string;
  transition?: { from: string; to: string };
  changes: { field: string; before: unknown; after: unknown }[];
  blockers: string[];
};
const stateNames: Record<string, string> = {
  RECEIVED: "Received",
  EXTRACTING: "Extracting",
  NEEDS_REVIEW: "Needs review",
  READY_TO_POST: "Ready to post",
  POSTED: "Posted",
  REJECTED: "Rejected",
  EXTRACTION_FAILED: "Extraction failed",
};
export const stateLabel = (state: unknown): string =>
  typeof state === "string"
    ? stateNames[state] || "Unrecognized status"
    : "Status not recorded";
export function auditView(event: Event): AuditView {
  const d = record(event.details);
  const revision =
    typeof d.revision === "number" && Number.isInteger(d.revision)
      ? `revision ${d.revision}`
      : "the recorded revision";
  const v: AuditView = {
    title: "Recorded activity",
    description:
      "An event was recorded. Open its technical details for the complete evidence.",
    icon: "info",
    tone: "neutral",
    changes: [],
    blockers: [],
  };
  if (typeof d.notes === "string" && d.notes.trim()) v.notes = d.notes;
  if (Array.isArray(d.blocker_codes))
    v.blockers = d.blocker_codes
      .filter((c): c is string => typeof c === "string")
      .map(ruleLabel);
  switch (event.event_type) {
    case "INVOICE_RECEIVED":
      v.title = "Invoice received";
      v.description = "The source document was received for processing.";
      v.icon = "document";
      break;
    case "DUPLICATE_UPLOAD_RETURNED":
      v.title = "Existing document recognized";
      v.description =
        "The same source document was already present. The existing invoice was returned.";
      v.icon = "document";
      break;
    case "STATE_CHANGED":
      v.title =
        (
          {
            EXTRACTING: "Invoice extraction started",
            NEEDS_REVIEW: "Invoice held for review",
            READY_TO_POST: "Invoice ready for posting",
            POSTED: "Invoice marked posted",
            REJECTED: "Invoice marked rejected",
            EXTRACTION_FAILED: "Invoice extraction failed",
          } as Record<string, string>
        )[text(d.to, "")] || "Invoice status changed";
      v.description =
        "The recorded invoice status changed. A status alone does not establish authenticity or human approval.";
      v.icon = "arrow";
      v.transition = { from: stateLabel(d.from), to: stateLabel(d.to) };
      break;
    case "VALIDATION_COMPLETED":
      v.title = "Validation completed";
      v.icon = "check";
      v.description =
        Array.isArray(d.blocker_codes) &&
        d.blocker_codes.every((c) => typeof c === "string" && c.trim())
          ? `${v.blockers.length} blocking check${v.blockers.length === 1 ? "" : "s"} recorded for ${revision}. Validation is separate from approval.`
          : "Validation was recorded; a complete blocker summary was not supplied.";
      v.tone = v.blockers.length ? "warning" : "neutral";
      break;
    case "INVOICE_CORRECTED":
      v.title = "Invoice corrected";
      v.description = `Corrections were saved as ${revision}. The original extraction is preserved; validation and approval are separate.`;
      v.icon = "edit";
      v.changes = Object.entries(record(d.diff))
        .filter(
          ([, value]) =>
            Object.hasOwn(record(value), "before") &&
            Object.hasOwn(record(value), "after"),
        )
        .map(([field, value]) => ({
          field,
          before: record(value).before,
          after: record(value).after,
        }));
      break;
    case "CORRECTION_NO_CHANGE":
      v.title = "Correction reviewed without changes";
      v.description = `No saved values changed for ${revision}.`;
      v.icon = "edit";
      break;
    case "INVOICE_APPROVED":
      v.title = "Invoice revision approved";
      v.description = `Human approval was recorded for ${revision}. It does not waive blocking checks or post a ledger entry.`;
      v.icon = "check";
      v.tone = "good";
      break;
    case "INVOICE_REJECTED":
      v.title = "Invoice rejected";
      v.description = `The operator rejected ${revision}. Its source and history remain available.`;
      v.icon = "stop";
      v.tone = "warning";
      break;
    case "APPROVAL_BLOCKED":
      v.title = "Approval blocked";
      v.description = `Approval did not complete for ${revision}. Review the recorded blocking checks.`;
      v.icon = "stop";
      v.tone = "warning";
      break;
    case "POST_BLOCKED":
      v.title = "Ledger posting blocked";
      v.description = `Posting did not complete for ${revision}. Review validation and current-revision approval requirements.`;
      v.icon = "stop";
      v.tone = "warning";
      break;
    case "LEDGER_POSTED":
      v.title = "Posted to internal ledger";
      v.description = `${financial(d.total, d.currency)} was recorded for ${revision}. This is not a payment or ERP writeback.`;
      v.icon = "ledger";
      v.tone = "good";
      break;
    case "VENDOR_CREATED":
      v.title = "Supplier registered";
      v.description = `${text(d.display_name, "A supplier")} was registered. Supplier policy does not itself approve an invoice.`;
      v.icon = "document";
      break;
  }
  return v;
}
