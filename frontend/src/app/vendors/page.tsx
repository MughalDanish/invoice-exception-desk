"use client";
import { useMemo, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus, Search, ArrowUpDown, ShieldCheck } from "lucide-react";
import type { Vendor } from "@/lib/api";
import { financial } from "@/lib/presentation";
import { Heading, useDesk } from "@/components/desk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTable } from "@/components/shared/data-table";
import { QueryError } from "@/components/shared/controls";
import { useSuppliers, useCreateSupplier } from "@/features/suppliers/queries";
type SupplierForm = {
  display_name: string;
  expected_currency: string;
  baseline_amount_limit: string;
  is_approved: boolean;
};
export default function VendorsPage() {
  const { readOnly } = useDesk();
  const query = useSuppliers();
  const create = useCreateSupplier();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const form = useForm<SupplierForm>({
    defaultValues: {
      display_name: "",
      expected_currency: "USD",
      baseline_amount_limit: "",
      is_approved: true,
    },
  });
  const columns = useMemo<ColumnDef<Vendor>[]>(
    () => [
      {
        accessorKey: "display_name",
        header: ({ column }) => (
          <button
            className="flex items-center gap-2"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Supplier
            <ArrowUpDown className="size-3" />
          </button>
        ),
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <span className="file-avatar">
              <ShieldCheck className="size-4" />
            </span>
            <strong className="text-[13px] font-medium">
              {row.original.display_name}
            </strong>
          </div>
        ),
      },
      {
        accessorKey: "expected_currency",
        header: "Currency policy",
        cell: ({ row }) => (
          <span className="text-xs">
            {row.original.expected_currency || "No currency policy"}
          </span>
        ),
      },
      {
        accessorKey: "baseline_amount_limit",
        header: "Review threshold",
        meta: { numeric: true },
        cell: ({ row }) => (
          <span className="financial-value">
            {row.original.baseline_amount_limit == null
              ? "No threshold"
              : financial(
                  row.original.baseline_amount_limit,
                  row.original.expected_currency,
                )}
          </span>
        ),
      },
      {
        accessorKey: "is_approved",
        header: "Approval",
        cell: ({ row }) => (
          <Badge
            variant="outline"
            className={
              row.original.is_approved
                ? "border-green-200 bg-green-50 text-green-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }
          >
            {row.original.is_approved ? "Approved" : "Unapproved"}
          </Badge>
        ),
      },
    ],
    [],
  );
  const filtered = (query.data || []).filter((row) =>
    row.display_name.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <Heading
        eyebrow="SUPPLIER CONTROLS"
        title="Suppliers"
        subtitle="Approved identities, currency policies and financial review thresholds."
      >
        {!readOnly && (
          <Button onClick={() => setOpen(true)}>
            <Plus className="size-4" />
            Register supplier
          </Button>
        )}
      </Heading>
      {query.error && (
        <QueryError error={query.error} retry={() => query.refetch()} />
      )}
      <section className="surface">
        <div className="table-toolbar">
          <div className="search-field">
            <Search className="size-4" />
            <Input
              aria-label="Search suppliers"
              placeholder="Search suppliers..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            {filtered.length} suppliers
          </span>
        </div>
        <DataTable
          columns={columns}
          data={filtered}
          rowId={(row) => row.id}
          clientSorting
          paused={query.isPaused}
          loading={query.isPending && !query.error}
          fetching={query.isFetching}
          emptyTitle={
            search ? "No matching suppliers" : "No registered suppliers"
          }
          emptyDescription={
            search
              ? "Try another supplier name."
              : "Register a verified supplier to establish a validation policy."
          }
        />
      </section>
      <p className="mt-4 text-xs text-muted-foreground">
        Supplier approval does not bypass invoice checks. Revalidate held
        invoices after registering a supplier.
      </p>
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!create.isPending) {
            setOpen(value);
            if (!value) {
              form.reset();
              create.reset();
            }
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Register supplier</DialogTitle>
            <DialogDescription>
              Set a policy for this supplier. Invoice validation and review
              still apply.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={form.handleSubmit(async (values) => {
              try {
                await create.mutateAsync({
                  ...values,
                  expected_currency:
                    values.expected_currency === "none"
                      ? null
                      : values.expected_currency,
                  baseline_amount_limit: values.baseline_amount_limit || null,
                });
                setOpen(false);
                form.reset();
              } catch {
                /* Persistent feedback below. */
              }
            })}
            className="space-y-4"
          >
            <div className="field">
              <Label htmlFor="supplier-name">Supplier name</Label>
              <Input
                id="supplier-name"
                {...form.register("display_name", {
                  required: "Enter a supplier name.",
                  maxLength: 200,
                })}
                disabled={create.isPending}
              />
              {form.formState.errors.display_name && (
                <p role="alert" className="text-xs text-destructive">
                  {form.formState.errors.display_name.message}
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="field">
                <Label>Expected currency</Label>
                <Controller
                  control={form.control}
                  name="expected_currency"
                  render={({ field }) => (
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      disabled={create.isPending}
                    >
                      <SelectTrigger aria-label="Expected currency">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No policy</SelectItem>
                        {["USD", "EUR", "GBP", "JPY"].map((c) => (
                          <SelectItem key={c} value={c}>
                            {c}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="field">
                <Label htmlFor="supplier-limit">Amount limit</Label>
                <Input
                  id="supplier-limit"
                  inputMode="decimal"
                  placeholder="5000.00"
                  disabled={create.isPending}
                  {...form.register("baseline_amount_limit", {
                    validate: (value) =>
                      !value ||
                      /^\d+(\.\d+)?$/.test(value) ||
                      "Enter an exact positive decimal amount.",
                  })}
                />
                {form.formState.errors.baseline_amount_limit && (
                  <p role="alert" className="text-xs text-destructive">
                    {form.formState.errors.baseline_amount_limit.message}
                  </p>
                )}
              </div>
            </div>
            <Controller
              control={form.control}
              name="is_approved"
              render={({ field }) => (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="supplier-approved"
                    checked={field.value}
                    onCheckedChange={(value) => field.onChange(value === true)}
                    disabled={create.isPending}
                  />
                  <Label htmlFor="supplier-approved">
                    Approved for invoice validation
                  </Label>
                </div>
              )}
            />
            <p className="text-xs text-muted-foreground">
              Use the supplier name from the invoice. Amount limits require a
              currency.
            </p>
            {create.error && <QueryError error={create.error} />}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={create.isPending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" loading={create.isPending}>
                Register supplier
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
