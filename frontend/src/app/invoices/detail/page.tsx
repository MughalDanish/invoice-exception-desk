import { Suspense } from "react";
import { InvoiceDetail } from "@/components/invoice-detail";
export default function Page() { return <Suspense fallback={<p>Loading invoice…</p>}><InvoiceDetail/></Suspense>; }
