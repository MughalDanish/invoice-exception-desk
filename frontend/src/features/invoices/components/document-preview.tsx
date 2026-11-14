"use client";
import { useEffect, useState } from "react";
import { FileText, Download, ExternalLink } from "lucide-react";
import { download, type Detail } from "@/lib/api";
import { useInvoiceDocument } from "../queries";
import {
  DocumentPreviewSkeleton,
  PausedState,
} from "@/components/shared/loading";
import { QueryError, IconAction } from "@/components/shared/controls";
export function DocumentPreview({ invoice }: { invoice: Detail }) {
  const query = useInvoiceDocument(invoice.id);
  const [url, setUrl] = useState("");
  // This effect owns a browser resource; the query owns all fetching and caching.
  /* eslint-disable react-hooks/set-state-in-effect -- Object URLs must be created and revoked with this browser resource's lifecycle. */
  useEffect(() => {
    if (!query.data) return;
    const next = URL.createObjectURL(query.data);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [query.data]);
  /* eslint-enable react-hooks/set-state-in-effect */
  return (
    <section className="document-pane" aria-label="Source document">
      <div className="document-toolbar">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="size-4 shrink-0" />
          <strong className="truncate text-xs">{invoice.filename}</strong>
        </div>
        <div className="flex">
          <IconAction
            icon={ExternalLink}
            label="Open source document"
            disabled={!url}
            onClick={() => window.open(url, "_blank", "noopener")}
          />
          <IconAction
            icon={Download}
            label="Download source document"
            disabled={!query.data}
            onClick={() => {
              if (query.data) download(query.data, invoice.filename);
            }}
          />
        </div>
      </div>
      <div className="document-body">
        {query.isPending ? (
          query.isPaused ? (
            <PausedState />
          ) : (
            <DocumentPreviewSkeleton />
          )
        ) : query.error ? (
          <QueryError error={query.error} retry={() => query.refetch()} />
        ) : url ? (
          invoice.mime_type === "application/pdf" ? (
            <iframe src={url} title="Original source document" />
          ) : (
            <img src={url} alt={`Original invoice ${invoice.filename}`} />
          )
        ) : (
          <DocumentPreviewSkeleton />
        )}
      </div>
      <div className="document-footer">
        Original file &middot; {Math.ceil(invoice.byte_size / 1024)} KB &middot;
        Read only
      </div>
    </section>
  );
}
