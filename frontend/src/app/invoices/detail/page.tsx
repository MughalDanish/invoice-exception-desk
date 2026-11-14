import { Suspense } from "react";
import { InvoiceDetail } from "@/components/invoice-detail";
import { InvoiceDetailSkeleton } from "@/components/shared/loading";
export default function Page() {
  return (
    <Suspense fallback={<InvoiceDetailSkeleton />}>
      <InvoiceDetail />
    </Suspense>
  );
}
