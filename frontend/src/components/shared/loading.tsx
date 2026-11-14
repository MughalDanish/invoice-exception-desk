"use client";
import { useSyncExternalStore } from "react";
import {
  onlineManager,
  useIsFetching,
  useIsMutating,
} from "@tanstack/react-query";
import { FileCheck2, LoaderCircle, WifiOff } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
export function AppLoader() {
  return (
    <div
      className="app-loader"
      role="status"
      aria-label="Connecting to workspace"
    >
      <span className="app-loader-mark">
        <FileCheck2 className="size-7" />
      </span>
      <strong>Invoice Desk</strong>
      <span className="text-muted-foreground text-sm">
        Preparing your workspace
      </span>
      <LoaderCircle className="size-4 animate-spin text-primary" />
    </div>
  );
}
export function InlineLoader({
  label = "Loading",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-xs text-muted-foreground",
        className,
      )}
      role="status"
    >
      <LoaderCircle className="size-3.5 animate-spin" />
      {label}
    </span>
  );
}
export function PausedState() {
  return (
    <div role="status" className="empty-state">
      <WifiOff className="size-5 text-muted-foreground" />
      <h3>Waiting for a connection</h3>
      <p>
        Reconnect to load this information. Requests resume when you are online.
      </p>
    </div>
  );
}
export function BackgroundActivity() {
  const fetching = useIsFetching();
  const mutating = useIsMutating();
  return fetching || mutating ? (
    <InlineLoader
      label={mutating ? "Saving" : "Refreshing"}
      className="hidden sm:inline-flex"
    />
  ) : null;
}
export function OfflineIndicator() {
  const online = useSyncExternalStore(
    onlineManager.subscribe,
    () => onlineManager.isOnline(),
    () => true,
  );
  return (
    !online && (
      <div className="notice error" role="status">
        <WifiOff className="size-4" />
        <span>
          You are offline. Existing information may be out of date. Reconnect
          before making a decision.
        </span>
      </div>
    )
  );
}
export function DataTableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div
      role="status"
      aria-label="Loading records"
      className="space-y-px"
      aria-busy="true"
    >
      <div className="grid grid-cols-4 gap-6 border-b bg-muted/40 px-5 py-3">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-3 w-20" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div
          className="grid grid-cols-4 items-center gap-6 border-b border-border/60 px-5 py-4"
          key={i}
        >
          <div className="space-y-2">
            <Skeleton className="h-3.5 w-28" />
            <Skeleton className="h-3 w-20" />
          </div>
          <Skeleton className="h-3.5 w-20" />
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-3.5 w-16" />
        </div>
      ))}
    </div>
  );
}
export function DashboardSkeleton() {
  return (
    <div
      className="space-y-6"
      aria-busy="true"
      role="status"
      aria-label="Loading overview"
    >
      <Skeleton className="h-7 w-36" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-4 rounded-lg border bg-card p-5">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-3 w-32" />
          </div>
        ))}
      </div>
      <div className="rounded-lg border bg-card">
        <DataTableSkeleton />
      </div>
    </div>
  );
}
export function DocumentPreviewSkeleton() {
  return (
    <div
      className="document-loading"
      role="status"
      aria-label="Loading source document"
    >
      <div className="document-paper">
        <Skeleton className="h-5 w-1/2" />
        <Skeleton className="mt-8 h-3 w-2/3" />
        <Skeleton className="mt-3 h-3 w-1/2" />
        <div className="mt-12 space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-3 w-full" />
          ))}
        </div>
      </div>
      <InlineLoader label="Loading original document" />
    </div>
  );
}
export function InvoiceDetailSkeleton() {
  return (
    <div role="status" aria-label="Loading invoice" aria-busy="true">
      <div className="mb-6 flex justify-between">
        <div className="space-y-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-3 w-32" />
        </div>
        <Skeleton className="h-8 w-28" />
      </div>
      <div className="grid min-h-[600px] gap-6 lg:grid-cols-2">
        <div className="rounded-lg border bg-card">
          <DocumentPreviewSkeleton />
        </div>
        <div className="space-y-6 rounded-lg border bg-card p-6">
          <Skeleton className="h-8 w-64" />
          <div className="grid grid-cols-2 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-9 w-full" />
              </div>
            ))}
          </div>
          <DataTableSkeleton rows={3} />
        </div>
      </div>
    </div>
  );
}
export function ActivitySkeleton() {
  return (
    <div className="space-y-5 p-5" role="status" aria-label="Loading activity">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="flex gap-3">
          <Skeleton className="size-7 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-48" />
            <Skeleton className="h-3 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
export function PageSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading page">
      <div className="space-y-3">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-3 w-64" />
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <DataTableSkeleton />
      </div>
    </div>
  );
}
export function UploadProgress({
  label = "Uploading and checking your document",
}: {
  label?: string;
}) {
  return (
    <div role="status" className="space-y-3 rounded-md bg-muted/50 p-4">
      <InlineLoader label={label} />
      <Progress
        value={null}
        aria-label="Processing in progress"
        className="indeterminate-progress h-1"
      />
      <p className="text-xs text-muted-foreground">
        Keep this window open. The result appears after the server finishes
        processing.
      </p>
    </div>
  );
}
