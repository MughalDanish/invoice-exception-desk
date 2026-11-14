"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowRight,
  CheckCheck,
  CircleAlert,
  Clock3,
  FileStack,
  Upload,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Heading, useDesk } from "@/components/desk";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DashboardSkeleton, PausedState } from "@/components/shared/loading";
import { QueryError } from "@/components/shared/controls";
import { InvoiceTable } from "@/features/invoices/invoice-table";
import { UploadDialog } from "@/features/invoices/upload-dialog";
import { useInvoiceList } from "@/features/invoices/queries";
import {
  auditView,
  financial,
  stateLabel,
  timestamp,
} from "@/lib/presentation";
import type { Stats } from "@/lib/api";
import { useOverview } from "./queries";
export function Overview() {
  const query = useOverview();
  const { readOnly } = useDesk();
  const [upload, setUpload] = useState(false);
  return (
    <>
      <Heading
        eyebrow="ACCOUNTS PAYABLE"
        title="Overview"
        subtitle="A clear view of your invoices and the work ahead."
      >
        {!readOnly && (
          <Button onClick={() => setUpload(true)}>
            <Upload className="size-4" />
            Upload invoice
          </Button>
        )}
      </Heading>
      {query.error && (
        <QueryError error={query.error} retry={() => query.refetch()} />
      )}
      {query.data ? (
        <OverviewContent stats={query.data} />
      ) : query.isPaused ? (
        <PausedState />
      ) : query.error ? null : (
        <DashboardSkeleton />
      )}
      {!readOnly && <UploadDialog open={upload} onOpenChange={setUpload} />}
    </>
  );
}
function OverviewContent({ stats }: { stats: Stats }) {
  const { readOnly } = useDesk();
  const needsReview = stats.by_status.NEEDS_REVIEW || 0;
  const ready = stats.by_status.READY_TO_POST || 0;
  const workStatus = needsReview
    ? "NEEDS_REVIEW"
    : ready
      ? "READY_TO_POST"
      : "";
  const work = useInvoiceList({ page: 1, limit: 5, status: workStatus });
  const distribution = Object.entries(stats.by_status)
    .filter(([, count]) => count > 0)
    .map(([status, count]) => ({ name: stateLabel(status), count }));
  const metrics = [
    {
      label: "Total invoices",
      count: stats.total_invoices,
      icon: FileStack,
      note: "Documents in your workspace",
      href: "/invoices/",
    },
    {
      label: "Needs review",
      count: needsReview,
      icon: CircleAlert,
      note: "Waiting for a human decision",
      href: "/exceptions/",
    },
    {
      label: "Ready to post",
      count: ready,
      icon: Clock3,
      note: "Passed current checks",
      href: "/invoices/",
    },
    {
      label: "Posted",
      count: stats.by_status.POSTED || 0,
      icon: CheckCheck,
      note: "Recorded in your ledger",
      href: "/ledger/",
    },
  ];
  return (
    <>
      <section className="metric-grid" aria-label="Invoice statistics">
        {metrics.map((metric, i) => (
          <Card
            key={metric.label}
            className={`metric-card ${i === 1 && needsReview ? "needs-attention" : ""}`}
          >
            <CardContent className="p-0">
              <div className="metric-label">
                <span>{metric.label}</span>
                <metric.icon className="size-4" />
              </div>
              <strong>{metric.count}</strong>
              <p>{metric.note}</p>
            </CardContent>
          </Card>
        ))}
      </section>
      <div className="overview-grid">
        <section className="surface worklist">
          <div className="section-header">
            <div>
              <div className="section-title-row">
                <h2>
                  {needsReview
                    ? "Needs your attention"
                    : ready
                      ? "Ready for the next step"
                      : "Recent invoices"}
                </h2>
                <span className="count-pill">
                  {needsReview || ready || stats.total_invoices}
                </span>
              </div>
              <p>
                {needsReview
                  ? "Review the exceptions before they reach your ledger."
                  : ready
                    ? "These invoices passed current checks. Posting is your decision."
                    : "The latest documents in your workspace."}
              </p>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href={needsReview ? "/exceptions/" : "/invoices/"}>
                View all
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </div>
          {work.error && (
            <QueryError
              compact
              error={work.error}
              retry={() => work.refetch()}
            />
          )}
          <InvoiceTable
            items={work.data?.items || []}
            loading={work.isPending}
            fetching={work.isFetching}
            previous={work.isPlaceholderData}
            compact
            readOnly={readOnly}
          />
        </section>
        <section className="surface pipeline">
          <div className="section-header">
            <div>
              <h2>Invoice pipeline</h2>
              <p>Current status distribution</p>
            </div>
          </div>
          <div
            className="pipeline-chart"
            aria-label="Invoice counts by current status"
          >
            {distribution.length ? (
              <ResponsiveContainer width="100%" height={180} minWidth={0}>
                <BarChart
                  data={distribution}
                  layout="vertical"
                  margin={{ top: 4, right: 24, bottom: 0, left: 0 }}
                  barSize={8}
                >
                  <CartesianGrid horizontal={false} stroke="#e5ebe6" />
                  <XAxis type="number" hide allowDecimals={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    width={103}
                    tick={{ fontSize: 11, fill: "#52675e" }}
                  />
                  <ChartTooltip
                    cursor={{ fill: "#eff3ef" }}
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 6,
                      borderColor: "#d5ded8",
                    }}
                    formatter={(value) => [value, "Invoices"]}
                  />
                  <Bar dataKey="count" fill="#367a64" radius={[0, 3, 3, 0]}>
                    <LabelList
                      dataKey="count"
                      position="right"
                      fontSize={11}
                      fill="#172d27"
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">
                No invoices received yet.
              </p>
            )}
          </div>
          <div className="pipeline-foot">
            <span>Duplicates flagged</span>
            <strong>{stats.duplicate_invoices}</strong>
          </div>
          <div className="pipeline-foot">
            <span>Extraction failed</span>
            <strong>{stats.by_status.EXTRACTION_FAILED || 0}</strong>
          </div>
        </section>
      </div>
      <div className="overview-bottom">
        <section className="surface">
          <div className="section-header">
            <div>
              <h2>Recent activity</h2>
              <p>A record of what happened in your workspace</p>
            </div>
            <span className="text-xs text-muted-foreground">
              Latest {Math.min(stats.recent_activity.length, 5)}
            </span>
          </div>
          <div className="recent-activity">
            {stats.recent_activity.slice(0, 5).map((event) => (
              <div className="recent-event" key={event.id}>
                <span className="recent-event-icon">
                  <Clock3 className="size-3.5" />
                </span>
                <div>
                  {event.invoice_id ? (
                    <Link href={`/invoices/detail/?id=${event.invoice_id}`}>
                      {auditView(event).title}
                    </Link>
                  ) : (
                    <strong>{auditView(event).title}</strong>
                  )}
                  <span>{event.actor}</span>
                </div>
                <time>{timestamp(event.created_at)}</time>
              </div>
            ))}
            {!stats.recent_activity.length && (
              <p className="p-5 text-sm text-muted-foreground">
                Activity appears after your first invoice.
              </p>
            )}
          </div>
        </section>
        <section className="surface ledger-summary">
          <div className="section-header">
            <div>
              <h2>Posted value</h2>
              <p>Immutable internal ledger entries</p>
            </div>
            <FileStack className="size-4 text-muted-foreground" />
          </div>
          <div className="ledger-values">
            {Object.entries(stats.posted_totals_by_currency).map(
              ([currency, amount]) => (
                <div key={currency}>
                  <span>{currency}</span>
                  <strong>
                    {financial(amount, currency).replace(`${currency} `, "")}
                  </strong>
                </div>
              ),
            )}
            {!Object.keys(stats.posted_totals_by_currency).length && (
              <p>No entries have been posted yet.</p>
            )}
          </div>
          <div className="ledger-summary-footer">
            <span>Totals remain separate by currency.</span>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ledger/">
                View ledger
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </div>
        </section>
      </div>
    </>
  );
}
