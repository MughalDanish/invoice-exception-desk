"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, ArrowUpRight, BookOpen } from "lucide-react";
import type { Ledger } from "@/lib/api";
import { financial, timestamp } from "@/lib/presentation";
import { Heading, Pager, useDesk } from "@/components/desk";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/shared/data-table";
import { QueryError } from "@/components/shared/controls";
import { useLedger, useExportLedger } from "@/features/ledger/queries";
export default function LedgerPage() {
  const { readOnly } = useDesk();
  const [page, setPage] = useState(1);
  const query = useLedger(page);
  const exporting = useExportLedger();
  const columns = useMemo<ColumnDef<Ledger>[]>(
    () => [
      {
        accessorKey: "invoice_number",
        header: "Invoice",
        cell: ({ row }) => (
          <Link
            className="invoice-identity"
            href={`/invoices/detail/?id=${row.original.invoice_id}`}
          >
            <span className="file-avatar">
              <BookOpen className="size-4" />
            </span>
            <span>
              <strong>{row.original.invoice_number}</strong>
              <span>{row.original.vendor_name}</span>
            </span>
          </Link>
        ),
      },
      {
        accessorKey: "total",
        header: "Posted amount",
        meta: { numeric: true },
        cell: ({ row }) => (
          <strong className="financial-value">
            {financial(row.original.total, row.original.currency)}
          </strong>
        ),
      },
      {
        accessorKey: "posted_at",
        header: "Posted",
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {timestamp(row.original.posted_at)}
          </span>
        ),
      },
      {
        accessorKey: "posted_by",
        header: "Operator",
        cell: ({ row }) => (
          <span className="text-xs">{row.original.posted_by}</span>
        ),
      },
      {
        id: "view",
        header: "",
        size: 45,
        cell: ({ row }) => (
          <Button asChild variant="ghost" size="icon-sm">
            <Link
              href={`/invoices/detail/?id=${row.original.invoice_id}`}
              aria-label={`View ${row.original.invoice_number}`}
            >
              <ArrowUpRight className="size-4" />
            </Link>
          </Button>
        ),
      },
    ],
    [],
  );
  return (
    <>
      <Heading
        eyebrow="LEDGER"
        title="Ledger"
        subtitle="Finalized invoice records. Every entry is an immutable snapshot."
      >
        {!readOnly && (
          <Button
            variant="outline"
            loading={exporting.isPending}
            onClick={() => exporting.mutate()}
          >
            <Download className="size-4" />
            Export CSV
          </Button>
        )}
      </Heading>
      {query.error && (
        <QueryError error={query.error} retry={() => query.refetch()} />
      )}
      <section className="surface">
        <div className="section-header">
          <div>
            <h2>
              Posted entries{" "}
              <span className="count-pill">{query.data?.total ?? 0}</span>
            </h2>
            <p>Original currency and exact financial amounts</p>
          </div>
        </div>
        <DataTable
          columns={columns}
          data={query.data?.items || []}
          rowId={(row) => row.id}
          href={(row) => `/invoices/detail/?id=${row.invoice_id}`}
          paused={query.isPaused}
          loading={query.isPending && !query.error}
          fetching={query.isFetching}
          previous={query.isPlaceholderData}
          emptyTitle="No posted entries"
          emptyDescription="Posted invoices will appear here after validation and any required approval."
        />
        <Pager
          page={page}
          total={query.data?.total || 0}
          onChange={setPage}
          disabled={query.isFetching || query.isPlaceholderData}
        />
      </section>
      <p className="mt-4 text-xs text-muted-foreground">
        CSV exports posted records with spreadsheet-safe values. This internal
        ledger does not make payments.
      </p>
    </>
  );
}
