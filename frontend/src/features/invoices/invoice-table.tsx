"use client";
import Link from "next/link";
import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowUpRight, Copy, Ellipsis, FileText } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/desk";
import { DataTable } from "@/components/shared/data-table";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { financial, ruleLabel } from "@/lib/presentation";
import type { Invoice } from "@/lib/api";
export const invoiceHref = (row: Invoice) => `/invoices/detail/?id=${row.id}`;
export function InvoiceTable({
  items,
  loading,
  paused,
  fetching,
  previous,
  compact = false,
  filtered = false,
  readOnly = false,
}: {
  items: Invoice[];
  loading?: boolean;
  paused?: boolean;
  fetching?: boolean;
  previous?: boolean;
  compact?: boolean;
  filtered?: boolean;
  readOnly?: boolean;
}) {
  const columns = useMemo<ColumnDef<Invoice>[]>(
    () => [
      {
        id: "invoice",
        header: "Invoice / Supplier",
        size: 280,
        cell: ({ row }) => {
          const i = row.original;
          return (
            <div className="invoice-identity">
              <span className="file-avatar">
                <FileText className="size-4" />
              </span>
              <div>
                <Link href={invoiceHref(i)} className="invoice-link">
                  {i.current_data?.invoice_number || i.filename}
                </Link>
                <span className="cell-secondary">
                  {i.current_data?.vendor_name || "Awaiting extraction"}
                </span>
              </div>
            </div>
          );
        },
      },
      {
        id: "date",
        header: "Invoice date",
        cell: ({ row }) => (
          <span className="cell-date">
            {row.original.current_data?.invoice_date || "Not provided"}
          </span>
        ),
      },
      {
        id: "amount",
        header: "Amount",
        meta: { numeric: true },
        cell: ({ row }) => (
          <span className="financial-amount">
            {financial(
              row.original.current_data?.total,
              row.original.current_data?.currency,
            )}
          </span>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <Badge status={row.original.status} />,
      },
      ...(!compact
        ? [
            {
              id: "issues",
              header: "Exceptions",
              cell: ({ row }: { row: { original: Invoice } }) =>
                row.original.issue_codes.length ? (
                  <span className="issue-label">
                    {ruleLabel(row.original.issue_codes[0])}
                    {row.original.issue_codes.length > 1 && (
                      <small> +{row.original.issue_codes.length - 1}</small>
                    )}
                  </span>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    No current exceptions
                  </span>
                ),
            },
          ]
        : []),
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        size: 48,
        cell: ({ row }) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Actions for ${row.original.current_data?.invoice_number || row.original.filename}`}
              >
                <Ellipsis className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={invoiceHref(row.original)}>
                  <ArrowUpRight className="size-4" />
                  Open invoice
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      row.original.current_data?.invoice_number ||
                        row.original.filename,
                    );
                    toast.success("Invoice reference copied.");
                  } catch {
                    toast.error("Clipboard access is unavailable.");
                  }
                }}
              >
                <Copy className="size-4" />
                Copy invoice reference
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [compact],
  );
  return (
    <DataTable
      columns={columns}
      data={items}
      loading={loading}
      paused={paused}
      fetching={fetching}
      previous={previous}
      href={invoiceHref}
      rowId={(row) => row.id}
      emptyTitle={filtered ? "No invoices match" : "No invoices here"}
      emptyDescription={
        filtered
          ? "Try another search or clear your filters."
          : readOnly
            ? "This snapshot has no records in this view."
            : "Upload an invoice to begin, or choose another view."
      }
    />
  );
}
