"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  ArrowLeft,
  MoreHorizontal,
  Code2,
  RefreshCw,
  FileWarning,
} from "lucide-react";
import { useDesk, Badge, Notice } from "./desk";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "./ui/resizable";
import { Button } from "./ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "./ui/dropdown-menu";
import { QueryError, IconAction } from "./shared/controls";
import {
  PausedState,
  ActivitySkeleton,
  InvoiceDetailSkeleton,
  UploadProgress,
} from "./shared/loading";
import { AuditTimeline } from "./evidence/audit-timeline";
import { OriginalExtraction } from "./evidence/original-extraction";
import { ValidationResults } from "./evidence/validation-results";
import { RecordContext } from "./evidence/record-context";
import {
  useInvoice,
  useInvoiceAudit,
  useInvoiceAction,
  processingPoll,
} from "@/features/invoices/queries";
import { DocumentPreview } from "@/features/invoices/components/document-preview";
import { InvoiceEditor } from "@/features/invoices/components/invoice-editor";
export function InvoiceDetail() {
  const id = useSearchParams().get("id") || "";
  const { readOnly, inspect } = useDesk();
  const query = useInvoice(id);
  const audit = useInvoiceAudit(id);
  const mutation = useInvoiceAction(id);
  const [dirty, setDirty] = useState(false);
  if (!/^[a-f0-9-]{36}$/i.test(id))
    return (
      <Notice error>
        Choose an invoice from <Link href="/invoices/">All invoices</Link>.
      </Notice>
    );
  if (query.isPending && !query.error)
    return query.isPaused ? <PausedState /> : <InvoiceDetailSkeleton />;
  if (!query.data)
    return (
      <>
        <Button variant="ghost" asChild>
          <Link href="/invoices/">
            <ArrowLeft />
            All invoices
          </Link>
        </Button>
        <QueryError error={query.error} retry={() => query.refetch()} />
      </>
    );
  const invoice = query.data;
  const events = audit.data || [];
  const processing = ["RECEIVED", "EXTRACTING", "EXTRACTION_FAILED"].includes(
    invoice.status,
  );
  return (
    <>
      <div className="invoice-heading">
        <div className="flex min-w-0 items-start gap-3">
          <Button
            asChild
            variant="outline"
            size="icon-sm"
            className="mt-1 shrink-0"
          >
            <Link href="/invoices/" aria-label="Back to invoices">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1>
                {invoice.current_data?.invoice_number || invoice.filename}
              </h1>
              <Badge status={invoice.status} />
            </div>
            <p>
              {invoice.current_data?.vendor_name || "Awaiting extraction"}{" "}
              &middot; Revision {invoice.revision}
            </p>
          </div>
        </div>
        <div className="heading-actions">
          <IconAction
            icon={RefreshCw}
            label="Refresh invoice"
            loading={query.isFetching}
            disabled={mutation.isPending}
            onClick={() => {
              void query.refetch();
              void audit.refetch();
            }}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="icon-sm"
                aria-label="Invoice options"
              >
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onSelect={() =>
                  inspect("Invoice technical details", {
                    invoice,
                    audit: audit.data ?? null,
                  })
                }
              >
                <Code2 className="size-4" />
                Technical details
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {query.error && (
        <QueryError error={query.error} retry={() => query.refetch()} />
      )}
      <ResizablePanelGroup
        orientation="horizontal"
        className="review-workspace"
      >
        <ResizablePanel
          defaultSize="46%"
          minSize="30%"
          className="source-panel"
        >
          <DocumentPreview key={id} invoice={invoice} />
        </ResizablePanel>
        <ResizableHandle
          withHandle
          aria-label="Resize document and review panels"
          className="review-resize-handle"
        />
        <ResizablePanel
          defaultSize="54%"
          minSize="35%"
          className="fields-panel"
        >
          <section className="review-pane surface">
            <Tabs defaultValue="review">
              <div className="review-tabs">
                <TabsList variant="line" aria-label="Invoice detail">
                  <TabsTrigger value="review">Review invoice</TabsTrigger>
                  <TabsTrigger value="original">
                    Original extraction
                  </TabsTrigger>
                  <TabsTrigger value="activity">Activity history</TabsTrigger>
                </TabsList>
              </div>
              <TabsContent
                value="review"
                forceMount
                className="m-0 data-[state=inactive]:hidden"
              >
                <RecordContext
                  invoice={invoice}
                  events={events}
                  dirty={dirty}
                />
                {processing && (
                  <section className="processing-panel">
                    <FileWarning className="size-6 text-muted-foreground" />
                    <h2>
                      {invoice.status === "EXTRACTION_FAILED"
                        ? "Extraction needs attention"
                        : invoice.status === "RECEIVED"
                          ? "Document ready for extraction"
                          : "Extraction in progress"}
                    </h2>
                    <p>
                      {invoice.status === "EXTRACTING" &&
                      processingPoll(invoice.status, invoice.updated_at)
                        ? "Checking for a completed extraction. You can leave this page safely."
                        : "Review the source document before starting a processing attempt."}
                    </p>
                    {mutation.isPending && (
                      <UploadProgress label="Processing document" />
                    )}
                    {mutation.error && <QueryError error={mutation.error} />}
                    <div className="space-y-1 text-xs text-muted-foreground">
                      {invoice.processing_attempts.map((attempt) => (
                        <p key={attempt.ordinal}>
                          Attempt {attempt.ordinal}: {attempt.status}
                          {attempt.error_code ? ` · ${attempt.error_code}` : ""}
                        </p>
                      ))}
                    </div>
                    {!readOnly && (
                      <Button
                        loading={mutation.isPending}
                        onClick={() =>
                          mutation.mutate({
                            action:
                              invoice.status === "RECEIVED"
                                ? "process"
                                : "retry",
                            revision: invoice.revision,
                          })
                        }
                      >
                        {invoice.status === "RECEIVED"
                          ? "Extract document"
                          : "Retry extraction"}
                      </Button>
                    )}
                  </section>
                )}
                {invoice.current_data && !processing && (
                  <>
                    <ValidationResults
                      rules={invoice.validations}
                      currency={invoice.current_data.currency}
                      revision={invoice.revision}
                      checked={invoice.validated_revision === invoice.revision}
                    />
                    <InvoiceEditor
                      key={id}
                      invoice={invoice}
                      refreshing={query.isFetching || !!query.error}
                      onDirty={setDirty}
                    />
                  </>
                )}
              </TabsContent>
              <TabsContent value="original" className="m-0">
                <OriginalExtraction
                  original={invoice.extracted_data}
                  current={invoice.current_data}
                />
              </TabsContent>
              <TabsContent value="activity" className="m-0">
                {audit.isPending ? (
                  audit.isPaused ? (
                    <PausedState />
                  ) : (
                    <ActivitySkeleton />
                  )
                ) : audit.error ? (
                  <QueryError
                    error={audit.error}
                    retry={() => audit.refetch()}
                  />
                ) : (
                  <AuditTimeline events={events} />
                )}
              </TabsContent>
            </Tabs>
          </section>
        </ResizablePanel>
      </ResizablePanelGroup>
    </>
  );
}
