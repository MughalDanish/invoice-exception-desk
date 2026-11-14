"use client";
import { useState, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { FileSearch } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTableSkeleton, PausedState } from "./loading";
import { cn } from "@/lib/utils";
type Props<T> = {
  columns: ColumnDef<T>[];
  data: T[];
  loading?: boolean;
  paused?: boolean;
  fetching?: boolean;
  previous?: boolean;
  href?: (row: T) => string;
  rowId: (row: T) => string;
  emptyTitle?: string;
  emptyDescription?: string;
  clientSorting?: boolean;
};
export function DataTable<T>({
  columns,
  data,
  loading,
  paused,
  fetching,
  previous,
  href,
  rowId,
  emptyTitle = "No records yet",
  emptyDescription = "Records will appear here when they are available.",
  clientSorting = false,
}: Props<T>) {
  const router = useRouter();
  const [sorting, setSorting] = useState<SortingState>([]);
  const table = useReactTable({
    data,
    columns,
    getRowId: rowId,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: clientSorting ? getSortedRowModel() : undefined,
    manualPagination: true,
    manualFiltering: true,
    manualSorting: !clientSorting,
    state: { sorting },
    onSortingChange: setSorting,
  });
  function navigate(event: MouseEvent<HTMLTableRowElement>, url: string) {
    if (
      !event.currentTarget.contains(event.target as Node) ||
      (event.target as Element).closest(
        "a,button,input,summary,[role=menuitem],[role=checkbox]",
      )
    )
      return;
    if (event.metaKey || event.ctrlKey) window.open(url, "_blank", "noopener");
    else router.push(url);
  }
  if (loading) return paused ? <PausedState /> : <DataTableSkeleton />;
  return (
    <div className="data-table" aria-busy={fetching || undefined}>
      {previous && (
        <p className="previous-results" role="status">
          Updating results. Previous records are shown temporarily.
        </p>
      )}
      <div
        className="table-scroll"
        tabIndex={0}
        role="region"
        aria-label="Financial records, scroll horizontally if needed"
      >
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id}>
                {group.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    style={{ width: header.column.columnDef.size }}
                    className={cn(
                      (
                        header.column.columnDef.meta as
                          | { numeric?: boolean }
                          | undefined
                      )?.numeric && "text-right",
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className={cn(href && "clickable-row")}
                tabIndex={href ? 0 : undefined}
                onClick={
                  href ? (e) => navigate(e, href(row.original)) : undefined
                }
                onKeyDown={
                  href
                    ? (e) => {
                        if (
                          e.target === e.currentTarget &&
                          (e.key === "Enter" || e.key === " ")
                        ) {
                          e.preventDefault();
                          router.push(href(row.original));
                        }
                      }
                    : undefined
                }
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cn(
                      (
                        cell.column.columnDef.meta as
                          | { numeric?: boolean }
                          | undefined
                      )?.numeric && "text-right tabular-nums",
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {!data.length && (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      )}
    </div>
  );
}
export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <FileSearch className="size-6" />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
