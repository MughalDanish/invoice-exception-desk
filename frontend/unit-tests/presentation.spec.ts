import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import {
  auditView,
  decimal,
  financial,
  outcome,
  record,
  ruleGuidance,
  ruleLabel,
  stateLabel,
  text,
  timestamp,
  validationGroups,
} from "../src/lib/presentation";
import type { Event, Rule } from "../src/lib/api";

for (const [input, expected] of [
  ["1150.00", "1,150.00"],
  ["9999999999999999.99", "9,999,999,999,999,999.99"],
  ["-1234567.001200", "-1,234,567.001200"],
  ["0.0000", "0.0000"],
  ["1234", "1,234"],
  ["1E+12", "1E+12"],
  ["not a decimal", "not a decimal"],
  [null, "Not provided"],
  [undefined, "Not provided"],
  [1234.56, "Not provided"],
  ["", "Not provided"],
] as const)
  test(`decimal preserves ${String(input)}`, () =>
    expect(decimal(input)).toBe(expected));

test("currency semantics stay explicit without rounding or precision repair", () => {
  expect(financial("1234", "JPY")).toBe("JPY 1,234");
  expect(financial("1234.00", "JPY")).toBe("JPY 1,234.00"); // Preserve a questionable scale for validation, never silently repair it.
  expect(financial("1234.5670", "USD")).toBe("USD 1,234.5670");
  expect(financial("1234.50", "EUR")).toBe("EUR 1,234.50");
  expect(financial("1234.50", "GBP")).toBe("GBP 1,234.50");
  expect(financial("10.00", null)).toBe("Currency not provided 10.00");
  expect(financial("10.00", "ZZZ")).toBe("ZZZ 10.00");
  expect(financial(null, "USD")).toBe("Not provided");
});
test("missing values are distinct from zero and invalid timestamps are safe", () => {
  expect(decimal("0")).toBe("0");
  expect(text(" ")).toBe("Not provided");
  expect(record(null)).toEqual({});
  expect(record([])).toEqual({});
  expect(timestamp("invalid")).toBe("Time not recorded");
  expect(timestamp(null)).toBe("Time not recorded");
  expect(timestamp("2026-11-13T12:00:00Z")).not.toContain("Invalid");
  expect(stateLabel("UNRECOGNIZED")).toBe("Unrecognized status");
});
const rule = (code: string, severity: string, passed: boolean): Rule => ({
  rule_code: code,
  severity,
  passed,
  message: "Evidence",
  expected: null,
  observed: null,
});
test("blocking failures outrank warnings and other failures; passed severity does not imply a block", () => {
  const input = [
    rule("W", "WARNING", false),
    rule("P", "BLOCKER", true),
    rule("U", "NEW", false),
    rule("B", "BLOCKER", false),
  ];
  const original = structuredClone(input);
  const groups = validationGroups(input);
  expect(groups.failed.map((r) => r.rule_code)).toEqual(["B", "W", "U"]);
  expect(groups.passed.map((r) => r.rule_code)).toEqual(["P"]);
  expect(groups.blocking).toBe(1);
  expect(groups.warnings).toBe(1);
  expect(outcome(input[1])).toBe("Passed");
  expect(outcome(input[0])).toBe("Warning");
  expect(outcome(input[2])).toBe("Failed check");
  expect(input).toEqual(original);
});
test("neutral validation names, safe unknowns and guidance never authorize a correction", () => {
  expect(ruleLabel("INVALID_DATE_RANGE")).toBe("Invoice date range");
  expect(ruleLabel("UNAPPROVED_VENDOR")).toBe("Supplier approval");
  expect(ruleLabel("FUTURE_RULE")).toBe("Additional validation check");
  expect(ruleGuidance("TOTAL_MISMATCH")).toContain("do not substitute");
  expect(ruleGuidance("FUTURE_RULE")).toContain("cannot be waived");
});
const event = (
  event_type: string,
  details?: Record<string, unknown>,
): Event => ({
  id: "event",
  actor: "actual-operator",
  event_type,
  details,
  created_at: "2026-11-13T12:00:00Z",
});
for (const [type, title] of Object.entries({
  INVOICE_RECEIVED: "Invoice received",
  DUPLICATE_UPLOAD_RETURNED: "Existing document recognized",
  INVOICE_CORRECTED: "Invoice corrected",
  CORRECTION_NO_CHANGE: "Correction reviewed without changes",
  INVOICE_APPROVED: "Invoice revision approved",
  INVOICE_REJECTED: "Invoice rejected",
  APPROVAL_BLOCKED: "Approval blocked",
  POST_BLOCKED: "Ledger posting blocked",
  LEDGER_POSTED: "Posted to internal ledger",
  VENDOR_CREATED: "Supplier registered",
}))
  test(`actual event mapping: ${type}`, () =>
    expect(auditView(event(type, { revision: 2 })).title).toBe(title));

test("correction uses the actual diff and notes without modifying or inventing an actor", () => {
  const e = event("INVOICE_CORRECTED", {
    from_revision: 1,
    revision: 2,
    notes: "Checked <script>source</script>",
    diff: {
      total: { before: "2500.00", after: "2300.00" },
      invoice_date: { before: null, after: "2026-11-13" },
    },
  });
  const copy = structuredClone(e);
  const v = auditView(e);
  expect(v.changes).toEqual([
    { field: "total", before: "2500.00", after: "2300.00" },
    { field: "invoice_date", before: null, after: "2026-11-13" },
  ]);
  expect(v.notes).toBe("Checked <script>source</script>");
  expect(v.description).toContain("revision 2");
  expect(e).toEqual(copy);
  expect(e.actor).toBe("actual-operator");
});
test("unknown, missing and malformed event details fail to readable fallbacks", () => {
  expect(auditView(event("NEW_FUTURE_EVENT"))).toMatchObject({
    title: "Recorded activity",
    changes: [],
    blockers: [],
  });
  expect(
    auditView(
      event("INVOICE_CORRECTED", {
        diff: { total: null, subtotal: { before: "1" } },
      }),
    ).changes,
  ).toEqual([]);
  expect(auditView(event("VALIDATION_COMPLETED")).description).toContain(
    "not supplied",
  );
  expect(
    auditView(event("VALIDATION_COMPLETED", { blocker_codes: [null, 12] }))
      .description,
  ).toContain("not supplied");
  expect(
    auditView(event("STATE_CHANGED", { from: "RECEIVED", to: "EXTRACTING" })),
  ).toMatchObject({
    title: "Invoice extraction started",
    transition: { from: "Received", to: "Extracting" },
  });
});
test("validation and human approval remain separate from authorization or posting", () => {
  expect(
    auditView(
      event("VALIDATION_COMPLETED", {
        revision: 2,
        blocker_codes: ["TOTAL_MISMATCH"],
      }),
    ),
  ).toMatchObject({ blockers: ["Invoice total"], tone: "warning" });
  expect(
    auditView(event("INVOICE_APPROVED", { revision: 2 })).description,
  ).toContain("does not waive");
  expect(
    auditView(
      event("LEDGER_POSTED", {
        revision: 2,
        total: "9999999999999999.99",
        currency: "USD",
      }),
    ).description,
  ).toContain("USD 9,999,999,999,999,999.99");
  expect(auditView(event("LEDGER_POSTED")).description).toContain(
    "Not provided",
  );
});
test("every actual public fixture rule and audit has a known presentation without data mutation", () => {
  const fixture = JSON.parse(
    readFileSync("../fixtures/public-demo.json", "utf8"),
  );
  const before = JSON.stringify(fixture);
  for (const invoice of fixture.invoices)
    for (const r of invoice.validations)
      expect(ruleLabel(r.rule_code)).not.toBe("Additional validation check");
  for (const events of Object.values(fixture.audits))
    for (const e of events as Event[])
      expect(auditView(e).title).not.toBe("Recorded activity");
  expect(JSON.stringify(fixture)).toBe(before);
});
