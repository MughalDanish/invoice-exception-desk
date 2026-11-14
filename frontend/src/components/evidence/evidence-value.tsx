import {
  decimal,
  fieldLabel,
  financial,
  monetaryField,
  record,
} from "@/lib/presentation";

// Render untrusted data as React text. Nested structures remain readable, not HTML.
export function EvidenceValue({
  value,
  currency,
  field = "",
  depth = 0,
  amountContext = false,
}: {
  value: unknown;
  currency?: unknown;
  field?: string;
  depth?: number;
  amountContext?: boolean;
}) {
  if (value === null || value === undefined)
    return <span className="evidence-muted">Not provided</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "string")
    return (
      <span>
        {monetaryField(field) ||
        (amountContext && ["expected", "observed"].includes(field))
          ? currency
            ? financial(value, currency)
            : decimal(value)
          : ["quantity", "tax_rate", "expected", "observed"].includes(field)
            ? decimal(value)
            : value || "Not provided"}
      </span>
    );
  if (typeof value === "number") return <span>{String(value)}</span>;
  if (depth >= 5)
    return (
      <span className="evidence-muted">
        Nested evidence is available in technical details.
      </span>
    );
  if (Array.isArray(value))
    return value.length ? (
      <ul className="evidence-values">
        {value.map((item, i) => (
          <li key={i}>
            {typeof item === "string" &&
            [
              "fields",
              "missing",
              "invalid_fields",
              "uncertain_fields",
            ].includes(field) ? (
              fieldLabel(item)
            ) : (
              <EvidenceValue
                value={item}
                currency={currency}
                field={field}
                depth={depth + 1}
                amountContext={amountContext}
              />
            )}
          </li>
        ))}
      </ul>
    ) : (
      <span className="evidence-muted">None recorded</span>
    );
  const entries = Object.entries(record(value));
  return entries.length ? (
    <dl className="evidence-facts nested-facts">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{fieldLabel(key)}</dt>
          <dd>
            <EvidenceValue
              value={item}
              currency={currency}
              field={key}
              depth={depth + 1}
              amountContext={amountContext}
            />
          </dd>
        </div>
      ))}
    </dl>
  ) : (
    <span className="evidence-muted">No details recorded</span>
  );
}
