"use client";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { binary, download, request, type Ledger, type Page } from "@/lib/api";
import { ledgerKeys } from "@/lib/query/keys";
import { readableError } from "@/lib/query/client";
export function useLedger(page: number) {

  return useQuery({
    queryKey: ledgerKeys.page(page),
    queryFn: ({ signal }) =>
      request<Page<Ledger>>(`/ledger?page=${page}&limit=20`, { signal }),
    placeholderData: keepPreviousData,
  });
}
export function useExportLedger() {

  return useMutation({
    mutationKey: ["ledger-export"],
    mutationFn: () => binary("/ledger/export.csv"),
    onSuccess: (blob) => {
      download(blob, "invoice-ledger.csv");
      toast.success("Posted ledger exported.");
    },
    onError: (error) => toast.error(readableError(error)),
  });
}
