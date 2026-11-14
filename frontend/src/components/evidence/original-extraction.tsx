import type { Payload } from "@/lib/api";
import { decimal, fieldLabel, financial, record } from "@/lib/presentation";
import { EvidenceValue } from "./evidence-value";
import { TechnicalDetails } from "./technical-details";

export function OriginalExtraction({
  original,
  current,
}: {
  original: Payload | null;
  current: Payload | null;
}) {
  const p = record(original);
  const now = record(current);
  const lines = Array.isArray(p.line_items) ? p.line_items.map(record) : [];
  const evidence = Object.entries(record(p.evidence));
  const uncertain = Array.isArray(p.uncertain_fields) ? p.uncertain_fields : [];
  const changed = Object.keys(p).filter(
    (key) => JSON.stringify(p[key]) !== JSON.stringify(now[key]),
  );
  return (
    <section
      className="panel evidence-panel original-extraction"
      aria-label="Original extraction"
    >
      <div className="panel-title">
        <div>
          <h2>Original extraction</h2>
          <p className="evidence-muted">
            Preserved source output · Read only · Not human verification
          </p>
        </div>
      </div>
      {original ? (
        <>
          <dl className="evidence-facts original-facts">
            {[
              "vendor_name",
              "vendor_tax_id",
              "invoice_number",
              "invoice_date",
              "due_date",
              "currency",
            ].map((key) => (
              <div key={key}>
                <dt>{fieldLabel(key)}</dt>
                <dd>
                  <EvidenceValue value={p[key]} />
                </dd>
              </div>
            ))}
          </dl>
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Original extracted line items, scroll horizontally"
          >
            <table className="evidence-table">
              <thead>
                <tr>
                  <th scope="col">Description</th>
                  <th scope="col" className="numeric">
                    Quantity
                  </th>
                  <th scope="col" className="numeric">
                    Unit price
                  </th>
                  <th scope="col" className="numeric">
                    Line total
                  </th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i}>
                    <td>
                      <EvidenceValue value={line.description} />
                    </td>
                    <td className="numeric">{decimal(line.quantity)}</td>
                    <td className="numeric">
                      {financial(line.unit_price, p.currency)}
                    </td>
                    <td className="numeric">
                      {financial(line.line_total, p.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!lines.length && (
              <p className="evidence-empty">No line items were supplied.</p>
            )}
          </div>
          <dl className="extracted-totals">
            {["subtotal", "tax_rate", "tax_amount", "total"].map((key) => (
              <div
                key={key}
                className={key === "total" ? "extracted-grand-total" : ""}
              >
                <dt>{fieldLabel(key)}</dt>
                <dd>
                  {key === "tax_rate"
                    ? decimal(p[key])
                    : financial(p[key], p.currency)}
                </dd>
              </div>
            ))}
          </dl>
          <div className="original-evidence">
            <h3>Extraction evidence</h3>
            <p className="evidence-muted">
              Source snippets are unverified text, not proof of authenticity or
              page citations.
            </p>
            {evidence.length ? (
              <dl className="evidence-facts">
                {evidence.map(([key, value]) => (
                  <div key={key}>
                    <dt>{fieldLabel(key)}</dt>
                    <dd>
                      <EvidenceValue value={value} />
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p>No source evidence was supplied.</p>
            )}
            <h3>Uncertain fields</h3>
            {uncertain.length ? (
              <EvidenceValue value={uncertain} field="uncertain_fields" />
            ) : (
              <p className="evidence-muted">
                None reported by extraction. This does not establish
                completeness or approval; missing values remain marked above.
              </p>
            )}
          </div>
          {current && (
            <details className="original-comparison">
              <summary>
                {changed.length
                  ? `${changed.length} fields differ from current saved information`
                  : "Compare with current saved information: no differences"}
              </summary>
              {changed.length > 0 && (
                <div className="table-scroll">
                  <table className="evidence-table">
                    <thead>
                      <tr>
                        <th scope="col">Field</th>
                        <th scope="col">Original extraction</th>
                        <th scope="col">Current saved</th>
                      </tr>
                    </thead>
                    <tbody>
                      {changed.map((key) => (
                        <tr key={key}>
                          <th scope="row">{fieldLabel(key)}</th>
                          <td>
                            <EvidenceValue
                              value={p[key]}
                              field={key}
                              currency={p.currency}
                            />
                          </td>
                          <td>
                            <EvidenceValue
                              value={now[key]}
                              field={key}
                              currency={now.currency}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="evidence-muted">
                Differences are not approval. See activity for recorded
                corrections, actors and reasons.
              </p>
            </details>
          )}
        </>
      ) : (
        <p className="evidence-empty">
          No original extraction was supplied. No values have been inferred.
        </p>
      )}
      <TechnicalDetails value={original} label="View source JSON" />
    </section>
  );
}
