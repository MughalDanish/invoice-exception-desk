"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDesk } from "@/components/desk";
import { request, type Stats } from "@/lib/api";
import { dashboardKeys } from "@/lib/query/keys";
export function useOverview() {
  const { readOnly } = useDesk();
  const [started] = useState(() => Date.now());
  return useQuery({
    queryKey: dashboardKeys.stats(),
    queryFn: ({ signal }) => request<Stats>("/stats", { signal }),
    staleTime: 20000,
    refetchInterval: (query) =>
      !readOnly &&
      Date.now() - started < 120000 &&
      (query.state.data?.by_status.EXTRACTING ?? 0) > 0
        ? 5000
        : false,
  });
}
