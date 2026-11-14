"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { request, type Vendor } from "@/lib/api";
import { supplierKeys } from "@/lib/query/keys";
import { readableError } from "@/lib/query/client";
export type SupplierInput = Pick<
  Vendor,
  "display_name" | "expected_currency" | "baseline_amount_limit" | "is_approved"
>;
export function useSuppliers() {

  return useQuery({
    queryKey: supplierKeys.all,
    queryFn: ({ signal }) => request<Vendor[]>("/vendors", { signal }),
    staleTime: 60000,
  });
}
export function useCreateSupplier() {

  const client = useQueryClient();
  return useMutation({
    mutationKey: ["supplier-create"],
    mutationFn: (data: SupplierInput) =>
      request<Vendor>("/vendors", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: supplierKeys.all });
      toast.success(
        "Supplier registered. Revalidate held invoices to apply this policy.",
      );
    },
    onError: (error) => toast.error(readableError(error)),
  });
}
