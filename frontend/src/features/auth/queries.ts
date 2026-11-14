"use client";
import { useQuery } from "@tanstack/react-query";
import { authApi } from "./api";
export const authKeys = { me: ["authentication", "me"] as const };
export function useCurrentUser(enabled: boolean) {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: ({ signal }) => authApi.me(signal),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}
