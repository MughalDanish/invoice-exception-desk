"use client";
import { useEffect, useState } from "react";
import { Search, Upload, X, RefreshCw } from "lucide-react";
import { Heading, Pager, useDesk } from "./desk";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { FilterSelect, IconAction, QueryError } from "./shared/controls";
import { InlineLoader } from "./shared/loading";
import { InvoiceTable } from "@/features/invoices/invoice-table";
import { UploadDialog } from "@/features/invoices/upload-dialog";
import { useInvoiceList } from "@/features/invoices/queries";
import { Overview } from "@/features/dashboard/overview";
import { ruleLabel, stateLabel } from "@/lib/presentation";
import { statuses } from "@/lib/api";
export { InvoiceTable } from "@/features/invoices/invoice-table";
const issues = [
  "TOTAL_MISMATCH",
  "SUBTOTAL_MISMATCH",
  "LINE_TOTAL_MISMATCH",
  "TAX_RATE_MISMATCH",
  "DUPLICATE_INVOICE",
  "UNAPPROVED_VENDOR",
  "MISSING_REQUIRED_FIELD",
  "INVALID_DATE",
  "INVALID_DATE_RANGE",
  "CURRENCY_MISMATCH",
  "AMOUNT_OUTLIER",
  "UNCERTAIN_EXTRACTION",
];
export function InvoiceList({
  mode = "all",
}: {
  mode?: "all" | "overview" | "exceptions";
}) {
  return mode === "overview" ? (
    <Overview />
  ) : (
    <InvoiceWorklist exceptions={mode === "exceptions"} />
  );
}
function InvoiceWorklist({ exceptions }: { exceptions: boolean }) {
  const { readOnly } = useDesk();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [issue, setIssue] = useState("");
  const [page, setPage] = useState(1);
  const [upload, setUpload] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const rows = useInvoiceList({
    page,
    limit: 20,
    search: query,
    status: exceptions ? "NEEDS_REVIEW" : status,
    issue,
  });
  const filtered = !!(search || status || issue);
  function reset() {
    setSearch("");
    setQuery("");
    setStatus("");
    setIssue("");
    setPage(1);
  }
  return (
    <>
      <Heading
        eyebrow="INVOICE OPERATIONS"
        title={exceptions ? "Exception queue" : "All invoices"}
        subtitle={
          exceptions
            ? "Resolve the issues holding invoices for review."
            : "Every document, from receipt to a final decision."
        }
      >
        <IconAction
          icon={RefreshCw}
          label="Refresh invoices"
          loading={rows.isFetching}
          onClick={() => rows.refetch()}
        />
        {!readOnly && (
          <Button onClick={() => setUpload(true)}>
            <Upload className="size-4" />
            Upload invoice
          </Button>
        )}
      </Heading>
      <section className="surface">
        <div className="table-toolbar">
          <div className="search-field">
            <Search className="size-4" />
            <Input
              aria-label="Search invoices"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search supplier, invoice or filename"
            />
            {search && (
              <IconAction
                icon={X}
                label="Clear search"
                onClick={() => {
                  setSearch("");
                  setPage(1);
                }}
              />
            )}
          </div>
          <div className="toolbar-filters">
            {!exceptions && (
              <FilterSelect
                label="Status"
                value={status}
                onChange={(value) => {
                  setStatus(value);
                  setPage(1);
                }}
                allLabel="All statuses"
                options={statuses.map((value) => ({
                  value,
                  label: stateLabel(value),
                }))}
              />
            )}
            <FilterSelect
              label="Issue type"
              value={issue}
              onChange={(value) => {
                setIssue(value);
                setPage(1);
              }}
              allLabel="All exceptions"
              options={issues.map((value) => ({
                value,
                label: ruleLabel(value),
              }))}
            />
            {filtered && (
              <Button variant="ghost" size="sm" onClick={reset}>
                Reset
              </Button>
            )}
          </div>
        </div>
        <div className="table-meta">
          <span>
            {rows.isPending
              ? "Loading invoices"
              : `${rows.data?.total ?? 0} invoices`}
            {exceptions && " requiring review"}
          </span>
          {rows.isFetching && !rows.isPending && (
            <InlineLoader label="Updating" />
          )}
        </div>
        {rows.error && (
          <QueryError error={rows.error} retry={() => rows.refetch()} />
        )}
        <InvoiceTable
          items={rows.data?.items || []}
          paused={rows.isPaused}
          loading={rows.isPending && !rows.error}
          fetching={rows.isFetching}
          previous={rows.isPlaceholderData}
          filtered={filtered}
          readOnly={readOnly}
        />
        <Pager
          page={page}
          total={rows.data?.total || 0}
          onChange={setPage}
          disabled={rows.isPlaceholderData || rows.isPending}
        />
      </section>
      {!readOnly && <UploadDialog open={upload} onOpenChange={setUpload} />}
    </>
  );
}
