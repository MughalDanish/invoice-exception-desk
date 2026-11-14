import type { QueryClient } from "@tanstack/react-query";
import {
  auditKeys,
  dashboardKeys,
  invoiceKeys,
  ledgerKeys,
} from "@/lib/query/keys";
export async function refreshInvoice(
  client: QueryClient,
  id: string,
  ledger = false,
) {
  await Promise.all([
    client.invalidateQueries({ queryKey: invoiceKeys.detail(id) }),
    client.invalidateQueries({ queryKey: auditKeys.invoice(id) }),
    client.invalidateQueries({ queryKey: invoiceKeys.lists() }),
    client.invalidateQueries({ queryKey: dashboardKeys.all }),
    ...(ledger ? [client.invalidateQueries({ queryKey: ledgerKeys.all })] : []),
  ]);
}
