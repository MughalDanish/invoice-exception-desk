import type { Event } from "@/lib/api";
import {
  FileText,
  ArrowRight,
  Check,
  Pencil,
  CircleX,
  BookOpen,
  Info,
} from "lucide-react";
import { auditView, fieldLabel, text, timestamp } from "@/lib/presentation";
import { EvidenceValue } from "./evidence-value";
const icons = {
  document: FileText,
  arrow: ArrowRight,
  check: Check,
  edit: Pencil,
  stop: CircleX,
  ledger: BookOpen,
  info: Info,
};
export function AuditTimeline({ events }: { events: Event[] }) {
  return (
    <section aria-label="Invoice activity">
      <div className="section-header">
        <div>
          <h2>Activity history</h2>
          <p>Recorded actions, corrections and decisions</p>
        </div>
        <span className="count-pill">{events.length}</span>
      </div>
      {events.length ? (
        <ol className="financial-timeline">
          {events.map((event) => {
            const view = auditView(event);
            const Icon = icons[view.icon];
            return (
              <li key={event.id} className={`timeline-event ${view.tone}`}>
                <span className="event-icon">
                  <Icon className="size-3.5" />
                </span>
                <article className="event-content">
                  <h3>{view.title}</h3>
                  <p className="event-meta">
                    {text(event.actor, "Actor not recorded")} &middot;{" "}
                    <time>{timestamp(event.created_at)}</time>
                  </p>
                  {!view.transition && !view.changes.length && <p>{view.description}</p>}
                  {view.transition && (
                    <p className="event-transition">
                      <span>{view.transition.from}</span>
                      <ArrowRight className="size-3" />
                      <span>{view.transition.to}</span>
                    </p>
                  )}
                  {view.blockers.length > 0 && (
                    <p className="event-blockers">
                      {view.blockers.join(" · ")}
                    </p>
                  )}
                  {view.changes.length > 0 && (
                    <div className="table-scroll">
                      <table className="evidence-table">
                        <caption className="sr-only">
                          Recorded correction: before and after
                        </caption>
                        <thead>
                          <tr>
                            <th>Field</th>
                            <th>Before</th>
                            <th>After</th>
                          </tr>
                        </thead>
                        <tbody>
                          {view.changes.map((change) => (
                            <tr key={change.field}>
                              <th scope="row">{fieldLabel(change.field)}</th>
                              <td>
                                <EvidenceValue
                                  value={change.before}
                                  field={change.field}
                                />
                              </td>
                              <td>
                                <EvidenceValue
                                  value={change.after}
                                  field={change.field}
                                />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {view.notes && (
                    <div className="event-notes">
                      <strong>Recorded reason / notes</strong>
                      <p>{view.notes}</p>
                    </div>
                  )}
                </article>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="evidence-empty">No activity supplied.</p>
      )}
    </section>
  );
}
