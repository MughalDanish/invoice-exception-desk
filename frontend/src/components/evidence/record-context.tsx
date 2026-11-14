import type { Detail, Event } from "@/lib/api";
import { record } from "@/lib/presentation";
export function RecordContext({
  invoice,
  events,
  dirty,
}: {
  invoice: Detail;
  events: Event[];
  dirty: boolean;
}) {
  const corrected = events.some(
    (e) =>
      e.event_type === "INVOICE_CORRECTED" &&
      record(e.details).revision === invoice.revision,
  );
  const approved = invoice.reviews.some(
    (r) => r.decision === "APPROVE" && r.revision === invoice.revision,
  );
  return (
    <section className="record-context" aria-label="Information provenance">
      <div>
        <span>Current information</span>
        <strong>
          Revision {invoice.revision}
          {dirty ? " · Unsaved edits" : corrected ? " · Corrected" : " · Saved"}
        </strong>
      </div>
      <div>
        <span>Validation</span>
        <strong>
          {invoice.validated_revision === invoice.revision
            ? `Validated revision ${invoice.revision}`
            : "Requires validation"}
        </strong>
      </div>
      <div>
        <span>Original extraction</span>
        <strong>
          {invoice.extracted_data ? "Preserved · Unverified" : "Not available"}
        </strong>
      </div>
      <div>
        <span>Human approval</span>
        <strong>
          {approved
            ? `Approved revision ${invoice.revision}`
            : "Not approved for this revision"}
        </strong>
      </div>
    </section>
  );
}
