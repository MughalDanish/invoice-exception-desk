import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api";
const duration = (value: string | undefined, fallback: number) =>
  value && Number.isFinite(Number(value)) && Number(value) >= 0
    ? Number(value)
    : fallback;
export const queryPolicy = {
  staleTime: duration(process.env.NEXT_PUBLIC_QUERY_STALE_TIME_MS, 15000),
  gcTime: duration(process.env.NEXT_PUBLIC_QUERY_GC_TIME_MS, 300000),
};
export const shouldRetryRead = (count: number, error: unknown) =>
  count < 1 &&
  !(error instanceof ApiError && error.status < 500) &&
  !(
    error instanceof DOMException &&
    ["AbortError", "TimeoutError"].includes(error.name)
  );
export function createQueryClient(onUnauthorized?: () => void) {
  const checkAuth = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) onUnauthorized?.();
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError: checkAuth }),
    mutationCache: new MutationCache({ onError: checkAuth }),
    defaultOptions: {
      queries: {
        ...queryPolicy,
        retry: shouldRetryRead,
        retryDelay: 1000,
        refetchOnWindowFocus: false,
      },
      // Never queue offline financial operations or replay them automatically.
      mutations: { retry: false, networkMode: "always", gcTime: 0 },
    },
  });
}
export function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Sign in again.";
    if (error.status === 409)
      return "This action could not be completed. Review the latest invoice, its checks and approval before trying again.";
    if (error.status === 404)
      return "This record could not be found or is no longer available.";
    if (error.status >= 500)
      return "The workspace is temporarily unavailable. Try refreshing shortly.";
    return error.message;
  }
  if (error instanceof DOMException && error.name === "TimeoutError")
    return "The request timed out. Refresh to check the latest state before trying again.";
  return "We could not connect. Check your connection and try again.";
}
