"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { readableError } from "@/lib/query/client";
import { investigationApi } from "./api";
import { activeRun, investigationKeys, safeEvidencePath } from "./presentation";
export function useInvestigations(invoice: string, offset: number) {
  return useQuery({ queryKey: investigationKeys.list(invoice, offset), queryFn: ({ signal }) => investigationApi.list(invoice, offset, signal), staleTime: 5000,
    refetchInterval: (q) => q.state.data?.items.some((run) => activeRun(run.status)) ? 2500 : false });
}
export function useInvestigation(run: string, revision: number) {
  return useQuery({ queryKey: [...investigationKeys.detail(run), revision], enabled: !!run,
    queryFn: ({ signal }) => investigationApi.detail(run, signal), staleTime: 5000,
    refetchInterval: (q) => activeRun(q.state.data?.status) ? 2500 : false });
}
export function useInvestigationEvents(run: string, after: number, active: boolean) {
  return useQuery({ queryKey: [...investigationKeys.events(run, after), active], enabled: !!run,
    queryFn: ({ signal }) => investigationApi.events(run, after, signal), staleTime: 5000,
    refetchInterval: active ? 2500 : false });
}
export function useInvestigationEvidence(invoice: string, href: string) {
  return useQuery({ queryKey: investigationKeys.evidence(invoice, href), enabled: !!safeEvidencePath(invoice, href),
    queryFn: ({ signal }) => investigationApi.evidence(invoice, href, signal), staleTime: Infinity });
}
export function useInvestigationCommand(invoice: string) {
  const client = useQueryClient();
  return useMutation({ mutationKey: ["investigation-command", invoice], retry: false,
    mutationFn: (command: { action: "start"; revision: number; key: string } | { action: "cancel" | "retry"; run: string }) =>
      command.action === "start" ? investigationApi.start(invoice, command.revision, command.key) : investigationApi.control(command.run, command.action),
    onSuccess: async (result, command) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["investigations", "invoice", invoice] }),
        client.invalidateQueries({ queryKey: investigationKeys.detail(result.run_id) }),
        client.invalidateQueries({ queryKey: ["investigations", "events", result.run_id] }),
      ]);
      toast.success(command.action === "start" ? "Investigation queued." : command.action === "cancel" ? "Investigation cancelled." : "Investigation retry queued.");
    }, onError: (error) => toast.error(readableError(error)),
  });
}
