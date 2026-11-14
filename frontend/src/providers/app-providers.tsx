"use client";
import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { QueryClientProvider } from "@tanstack/react-query";
import NextTopLoader, { useTopLoader } from "nextjs-toploader";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createQueryClient } from "@/lib/query/client";
function NavigationCompletion() {
  const pathname = usePathname();
  const loader = useTopLoader();
  useEffect(() => {
    loader.done(); /* Completion follows actual router state. */
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    let deadline: ReturnType<typeof setTimeout> | undefined;
    const stop = () => {
      clearTimeout(deadline);
      loader.done(true);
    };
    const click = (event: MouseEvent) => {
      const link = (event.target as Element).closest?.("a[href]");
      if (link && !event.ctrlKey && !event.metaKey) {
        clearTimeout(deadline);
        deadline = setTimeout(stop, 20000);
      }
    };
    document.addEventListener("click", click);
    window.addEventListener("error", stop);
    window.addEventListener("popstate", stop);
    return () => {
      clearTimeout(deadline);
      document.removeEventListener("click", click);
      window.removeEventListener("error", stop);
      window.removeEventListener("popstate", stop);
      loader.done(true);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}
export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(() => createQueryClient());
  useEffect(() => {
    // Delete the replaced demo credentials; new auth uses HttpOnly cookies only.
    for (const store of ["sessionStorage", "localStorage"] as const) {
      try { window[store].removeItem("invoice-desk.operator-session.v1"); } catch { /* Storage may be blocked. */ }
    }
  }, []);
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={200}>
        <NextTopLoader
          color="#155e51"
          height={2}
          showSpinner={false}
          shadow={false}
          showForHashAnchor={false}
        />
        <NavigationCompletion />
        {children}
        <Toaster position="bottom-right" closeButton richColors />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
