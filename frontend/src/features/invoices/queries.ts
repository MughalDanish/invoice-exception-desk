"use client";
import { useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { useDesk } from "@/components/desk";
import { readableError } from "@/lib/query/client";
import {
  auditKeys,
  dashboardKeys,
  invoiceKeys,
  type InvoiceFilters,
} from "@/lib/query/keys";
import { invoiceApi, type InvoiceCommand } from "./api";
import { processingPoll } from "./polling";
import { refreshInvoice } from "./invalidation";
export { processingPoll } from "./polling";
export function useInvoiceList(filters: InvoiceFilters) {
  const { readOnly } = useDesk();
  const [mountedAt] = useState(() => Date.now());
  return useQuery({
    queryKey: invoiceKeys.list(filters),
    queryFn: ({ signal }) => invoiceApi.list(filters, signal),
    placeholderData: keepPreviousData,
    refetchInterval: (query) =>
      !readOnly &&
      Date.now() - mountedAt < 120000 &&
      query.state.data?.items.some((i) =>
        processingPoll(i.status, i.updated_at),
      )
        ? 5000
        : false,
  });
}
export function useInvoice(id: string) {
  const { readOnly } = useDesk();
  const [mountedAt] = useState(() => Date.now());
  return useQuery({
    queryKey: invoiceKeys.detail(id),
    enabled: /^[a-f0-9-]{36}$/i.test(id),
    queryFn: ({ signal }) => invoiceApi.detail(id, signal),
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) =>
      !readOnly &&
      Date.now() - mountedAt < 120000 &&
      processingPoll(query.state.data?.status, query.state.data?.updated_at)
        ? 2500
        : false,
  });
}
export function useInvoiceAudit(id: string) {

  return useQuery({
    queryKey: auditKeys.invoice(id),
    enabled: /^[a-f0-9-]{36}$/i.test(id),
    queryFn: ({ signal }) => invoiceApi.audit(id, signal),
  });
}
export function useInvoiceDocument(id: string) {

  return useQuery({
    queryKey: invoiceKeys.document(id),
    enabled: /^[a-f0-9-]{36}$/i.test(id),
    queryFn: ({ signal }) => invoiceApi.document(id, signal),
    staleTime: Infinity,
    gcTime: 60000,
  });
}
const successMessages = {
  save: "Corrections saved. Revalidate this version before approval.",
  revalidate: "Validation completed.",
  approve: "Current version approved.",
  reject: "Invoice rejected.",
  post: "Invoice posted to the ledger.",
  process: "Extraction completed.",
  retry: "Extraction attempt completed.",
};
export function useInvoiceAction(id: string) {

  const client = useQueryClient();
  return useMutation({
    mutationKey: ["invoice-action", id],
    mutationFn: (command: InvoiceCommand) =>
      invoiceApi.action(id, command),
    onSuccess: async (result, command) => {
      await refreshInvoice(client, id, command.action === "post");
      if (result.status === "EXTRACTION_FAILED")
        toast.error(
          "Extraction failed. Review the document and retry when ready.",
        );
      else toast.success(successMessages[command.action]);
    },
    onError: async (error, command) => {
      await refreshInvoice(client, id, command.action === "post");
      toast.error(readableError(error));
    },
  });
}
export function useUploadInvoice() {

  const client = useQueryClient();
  return useMutation({
    mutationKey: ["invoice-upload"],
    mutationFn: (file: File) => invoiceApi.upload(file),
    onSuccess: async (result) => {
      await refreshInvoice(client, result.invoice_id);
      if (result.status === "EXTRACTION_FAILED")
        toast.error("Document received, but extraction failed.");
      else
        toast.success(
          result.duplicate
            ? "Existing invoice returned."
            : "Invoice uploaded and checked.",
        );
    },
    onError: async (error) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: invoiceKeys.lists() }),
        client.invalidateQueries({ queryKey: dashboardKeys.all }),
      ]);
      toast.error(readableError(error));
    },
  });
}
