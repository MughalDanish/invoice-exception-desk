"use client";
import { useState, useSyncExternalStore } from "react";
import { useForm, useFieldArray, useWatch } from "react-hook-form";
import { useQueryClient, onlineManager } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Save,
  ShieldCheck,
  Check,
  ArrowUpRight,
  ChevronDown,
} from "lucide-react";
import { type Detail, type Payload } from "@/lib/api";
import { financial, fieldLabel } from "@/lib/presentation";
import { invoiceKeys } from "@/lib/query/keys";
import { useDesk, Notice } from "@/components/desk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { QueryError } from "@/components/shared/controls";
import { useInvoiceAction } from "../queries";
import type { InvoiceAction } from "../api";
const identity = [
  "vendor_name",
  "vendor_tax_id",
  "invoice_number",
  "currency",
  "invoice_date",
  "due_date",
] as const;
const amounts = ["subtotal", "tax_rate", "tax_amount", "total"] as const;
const lineFields = [
  "description",
  "quantity",
  "unit_price",
  "line_total",
] as const;
export function InvoiceEditor({
  invoice,
  refreshing,
  onDirty,
}: {
  invoice: Detail;
  refreshing: boolean;
  onDirty: (dirty: boolean) => void;
}) {
  const { readOnly } = useDesk();
  const client = useQueryClient();
  const mutation = useInvoiceAction(invoice.id);
  // This snapshot belongs to the edit draft; React Query retains the authoritative server record.
  const [base, setBase] = useState(() => ({
    revision: invoice.revision,
    data: structuredClone(invoice.current_data!),
  }));
  const form = useForm<Payload>({
    defaultValues: structuredClone(invoice.current_data!),
  });
  const lines = useFieldArray({ control: form.control, name: "line_items" });
  const [notes, setNotes] = useState("");
  const [confirm, setConfirm] = useState<"approve" | "reject" | "post" | null>(
    null,
  );
  const values = useWatch({ control: form.control });
  const dirty = JSON.stringify(values) !== JSON.stringify(base.data);
  const online = useSyncExternalStore(
    onlineManager.subscribe,
    () => onlineManager.isOnline(),
    () => true,
  );
  // Report user edits through input events, never mirror the server record in local state.
  const stale = invoice.revision !== base.revision;
  const immutable = readOnly || ["POSTED", "REJECTED"].includes(invoice.status);
  const busy = mutation.isPending || refreshing || !online;
  const checked = invoice.validated_revision === invoice.revision;
  const blockers = invoice.validations.some(
    (r) => !r.passed && r.severity === "BLOCKER",
  );
  const approved = invoice.reviews.some(
    (r) => r.revision === invoice.revision && r.decision === "APPROVE",
  );
  const canDecide = !immutable && !busy && !dirty && !stale;
  function resetTo(latest: Detail) {
    if (!latest.current_data) return;
    setBase({
      revision: latest.revision,
      data: structuredClone(latest.current_data),
    });
    form.reset(structuredClone(latest.current_data));
    onDirty(false);
  }
  async function run(action: InvoiceAction) {
    const changes =
      action === "save"
        ? (Object.fromEntries(
            Object.entries(form.getValues()).filter(
              ([key, value]) =>
                JSON.stringify(value) !==
                JSON.stringify(base.data[key as keyof Payload]),
            ),
          ) as Partial<Payload>)
        : undefined;
    try {
      await mutation.mutateAsync({
        action,
        revision: invoice.revision,
        changes,
        notes,
      });
      if (action === "save") {
        const latest = client.getQueryData<Detail>(
          invoiceKeys.detail(invoice.id),
        );
        if (latest) resetTo(latest);
      }
      setConfirm(null);
      setNotes("");
    } catch {
      /* Persistent error below; the draft remains available. */
    }
  }
  function field(key: (typeof identity)[number] | (typeof amounts)[number]) {
    return (
      <div className="field" key={key}>
        <Label htmlFor={`field-${key}`}>{fieldLabel(key)}</Label>
        <Input
          id={`field-${key}`}
          disabled={immutable || mutation.isPending}
          inputMode={
            amounts.includes(key as (typeof amounts)[number])
              ? "decimal"
              : undefined
          }
          {...form.register(key, {
            setValueAs: (value) => (value === "" ? null : value),
          })}
        />
      </div>
    );
  }
  return (
    <>
      <form
        onSubmit={form.handleSubmit(() => run("save"))}
        onChange={() => {
          const next =
            JSON.stringify(form.getValues()) !== JSON.stringify(base.data);
          onDirty(next);
        }}
      >
        {stale && (
          <Notice error>
            The saved invoice changed. Reload the current revision before making
            a financial decision. Your edits remain in this form.
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => resetTo(invoice)}
            >
              Load saved revision
            </Button>
          </Notice>
        )}
        {mutation.error && <QueryError error={mutation.error} />}
        <fieldset disabled={immutable || mutation.isPending}>
          <section className="review-fieldset">
            <h2>Invoice information</h2>
            <div className="review-field-grid">{identity.map(field)}</div>
          </section>
          <section className="review-fieldset">
            <h2>
              Line items{" "}
              <span className="count-pill">{lines.fields.length}</span>
            </h2>
            <div className="table-scroll review-lines">
              <table className="w-full">
                <thead>
                  <tr>
                    {lineFields.map((k) => (
                      <th key={k}>{fieldLabel(k)}</th>
                    ))}
                    {!immutable && (
                      <th>
                        <span className="sr-only">Remove</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {lines.fields.map((line, index) => (
                    <tr key={line.id}>
                      {lineFields.map((key) => (
                        <td key={key}>
                          <Input
                            aria-label={`Line ${index + 1} ${fieldLabel(key)}`}
                            inputMode={
                              key === "description" ? undefined : "decimal"
                            }
                            {...form.register(`line_items.${index}.${key}`, {
                              setValueAs: (value) =>
                                value === "" ? null : value,
                            })}
                          />
                        </td>
                      ))}
                      {!immutable && (
                        <td>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Remove line ${index + 1}`}
                            onClick={() => {
                              lines.remove(index);
                              onDirty(true);
                            }}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!immutable && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mt-2"
                onClick={() => {
                  lines.append({
                    description: "",
                    quantity: "",
                    unit_price: "",
                    line_total: "",
                  });
                  onDirty(true);
                }}
              >
                <Plus className="size-3.5" />
                Add line
              </Button>
            )}
          </section>
          <section className="review-fieldset">
            <h2>Financial amounts</h2>
            <div className="review-field-grid">{amounts.map(field)}</div>
            <p className="mt-2 text-xs text-muted-foreground">
              Exact decimal values. Verify against the source; amounts are never
              recalculated in this form.
            </p>
          </section>
          <Collapsible className="review-fieldset">
            <CollapsibleTrigger className="flex w-full items-center justify-between text-xs font-medium">
              Extraction evidence and uncertainty
              <ChevronDown className="size-4" />
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-3 pt-4">
              <div className="field">
                <Label htmlFor="uncertain">
                  Uncertain fields (comma separated)
                </Label>
                <Input
                  id="uncertain"
                  {...form.register("uncertain_fields", {
                    setValueAs: (value) =>
                      typeof value === "string"
                        ? value
                            .split(",")
                            .map((v) => v.trim())
                            .filter(Boolean)
                        : value,
                  })}
                />
              </div>
              {Object.keys(invoice.current_data?.evidence || {}).map(
                (key, i) => (
                  <div key={key} className="field">
                    <Label htmlFor={`evidence-${i}`}>{fieldLabel(key)}</Label>
                    <Textarea
                      id={`evidence-${i}`}
                      {...form.register(`evidence.${key}`)}
                    />
                  </div>
                ),
              )}
            </CollapsibleContent>
          </Collapsible>
        </fieldset>
        {!immutable && (
          <div className="review-actions">
            <div className="review-notes">
              <Label htmlFor="review-notes">Reason / review notes</Label>
              <Textarea
                id="review-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={mutation.isPending}
                placeholder="Explain corrections or your review decision"
                maxLength={2000}
              />
            </div>
            <div className="review-actions-top">
              <span>
                {dirty
                  ? "Unsaved corrections"
                  : stale
                    ? "Newer revision available"
                    : `Saved revision ${invoice.revision}`}
              </span>
              <strong>
                {financial(
                  invoice.current_data?.total,
                  invoice.current_data?.currency,
                )}
              </strong>
            </div>
            <div className="review-actions-buttons">
              <Button
                type="submit"
                variant={dirty ? "default" : "outline"}
                disabled={!dirty || busy || stale || !notes.trim()}
                loading={
                  mutation.isPending && mutation.variables?.action === "save"
                }
              >
                <Save className="size-3.5" />
                Save corrections
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={!canDecide}
                onClick={() => run("revalidate")}
                loading={
                  mutation.isPending &&
                  mutation.variables?.action === "revalidate"
                }
              >
                <ShieldCheck className="size-3.5" />
                Revalidate
              </Button>
              {!approved && (
                <Button
                  type="button"
                  disabled={!canDecide || !checked || blockers}
                  onClick={() => setConfirm("approve")}
                >
                  <Check className="size-3.5" />
                  Approve revision
                </Button>
              )}
              <Button
                type="button"
                disabled={
                  !canDecide ||
                  !checked ||
                  blockers ||
                  (invoice.review_required && !approved)
                }
                onClick={() => setConfirm("post")}
              >
                <ArrowUpRight className="size-3.5" />
                Post to ledger
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="text-destructive"
                disabled={!canDecide}
                onClick={() => setConfirm("reject")}
              >
                Reject
              </Button>
            </div>
            {dirty && !notes.trim() && (
              <p className="mt-2 text-xs text-muted-foreground">
                Add a reason to save corrections.
              </p>
            )}
          </div>
        )}
        {immutable && (
          <div className="review-fieldset financial-summary">
            <span>
              {readOnly
                ? "Current saved total · Read only"
                : invoice.status === "POSTED"
                  ? "Posted total · Immutable record"
                  : "Rejected record"}
            </span>
            <strong>
              {financial(
                invoice.current_data?.total,
                invoice.current_data?.currency,
              )}
            </strong>
          </div>
        )}
      </form>
      <AlertDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open && !mutation.isPending) setConfirm(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm === "post"
                ? "Post this invoice to the ledger?"
                : confirm === "reject"
                  ? "Reject this invoice?"
                  : "Approve this revision?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {invoice.current_data?.invoice_number || invoice.filename}{" "}
              &middot; Revision {invoice.revision} &middot;{" "}
              {financial(
                invoice.current_data?.total,
                invoice.current_data?.currency,
              )}
              .{" "}
              {confirm === "post"
                ? "Posting creates an immutable ledger entry after fresh backend checks."
                : confirm === "reject"
                  ? "Rejection is final for this invoice. Record a reason below."
                  : "Approval applies only to this saved revision. Posting remains a separate action."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Label htmlFor="confirmation-notes">
            Reason / notes{confirm === "reject" ? " (required)" : ""}
          </Label>
          <Textarea
            id="confirmation-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={mutation.isPending}
            maxLength={2000}
          />
          {mutation.error && <QueryError error={mutation.error} />}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={mutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <Button
              loading={mutation.isPending}
              disabled={!canDecide || (confirm === "reject" && !notes.trim())}
              variant={confirm === "reject" ? "destructive" : "default"}
              onClick={() => {
                if (confirm) void run(confirm);
              }}
            >
              {confirm === "post"
                ? "Confirm posting"
                : confirm === "reject"
                  ? "Confirm rejection"
                  : "Confirm approval"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
