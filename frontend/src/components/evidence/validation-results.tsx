import type { Rule } from "@/lib/api";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import {
  outcome,
  ruleGuidance,
  ruleLabel,
  validationGroups,
} from "@/lib/presentation";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { EvidenceValue } from "./evidence-value";
function Check({ rule, currency }: { rule: Rule; currency?: string | null }) {
  const amountContext = [
    "TOTAL_MISMATCH",
    "SUBTOTAL_MISMATCH",
    "TAX_RATE_MISMATCH",
    "LINE_TOTAL_MISMATCH",
  ].includes(rule.rule_code);
  return (
    <article
      className={`financial-rule ${rule.passed ? "passed" : rule.severity === "BLOCKER" ? "blocked" : "warning"}`}
    >
      <div className="check-heading">
        <h3>
          {rule.passed ? (
            <CheckCircle2 className="size-4" />
          ) : (
            <ShieldAlert className="size-4" />
          )}
          {ruleLabel(rule.rule_code)}
        </h3>
        <span className="check-outcome">{outcome(rule)}</span>
      </div>
      <p>{rule.message || "No explanation supplied."}</p>
      {!rule.passed && (
        <>
          <div className="financial-rule-values">
            <div>
              <h4>Expected</h4>
              <EvidenceValue
                value={rule.expected}
                currency={currency}
                amountContext={amountContext}
              />
            </div>
            <div>
              <h4>Observed</h4>
              <EvidenceValue
                value={rule.observed}
                currency={currency}
                amountContext={amountContext}
              />
            </div>
          </div>
          <p className="check-guidance">{ruleGuidance(rule.rule_code)}</p>
        </>
      )}
    </article>
  );
}
export function ValidationResults({
  rules,
  currency,
  revision,
  checked,
}: {
  rules: Rule[];
  currency?: string | null;
  revision: number;
  checked: boolean;
}) {
  const groups = validationGroups(rules);
  return (
    <section className="validation-evidence" aria-label="Validation checks">
      <div className="section-header">
        <div>
          <h2>Validation checks</h2>
          <p>
            {checked
              ? `Saved revision ${revision}`
              : "Current revision needs validation"}
          </p>
        </div>
        <span className="validation-summary">
          {groups.blocking
            ? `${groups.blocking} blocking`
            : groups.failed.length
              ? `${groups.failed.length} need attention`
              : `${groups.passed.length} passed`}
        </span>
      </div>
      {groups.failed.map((rule, i) => (
        <Check key={`${rule.rule_code}-${i}`} rule={rule} currency={currency} />
      ))}
      {groups.passed.length > 0 && (
        <Accordion type="single" collapsible className="successful-checks">
          <AccordionItem value="passed" className="border-0">
            <AccordionTrigger className="py-3 text-xs">
              <span className="flex items-center gap-2">
                <CheckCircle2 className="size-4 text-green-700" />
                {groups.passed.length} successful checks
              </span>
            </AccordionTrigger>
            <AccordionContent>
              {groups.passed.map((rule, i) => (
                <Check
                  key={`${rule.rule_code}-${i}`}
                  rule={rule}
                  currency={currency}
                />
              ))}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )}
      {!rules.length && (
        <p className="evidence-empty">
          No checks recorded. Validation never implies approval.
        </p>
      )}
    </section>
  );
}
