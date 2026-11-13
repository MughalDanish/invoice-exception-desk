import type { Metadata } from "next";
import { DeskProvider } from "@/components/desk";
import "./globals.css";
export const metadata: Metadata = { title: "Invoice Exception Desk", description: "Catch invoice mistakes before they reach your ledger. Synthetic local demonstration." };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><DeskProvider>{children}</DeskProvider></body></html>;
}
