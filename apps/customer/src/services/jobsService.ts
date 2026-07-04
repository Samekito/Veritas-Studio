// TanStack Query hooks for the customer app — thin wrappers over the shared api
// client. Components consume these instead of fetching in effects.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@veritas/shared";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health });
}

export function useStats() {
  return useQuery({ queryKey: ["stats"], queryFn: api.stats });
}

export function useLibrary() {
  return useQuery({ queryKey: ["library"], queryFn: () => api.library().then((r) => r.jobs) });
}

export function usePassport(id: string | undefined) {
  return useQuery({ queryKey: ["passport", id], queryFn: () => api.passport(id!), enabled: !!id });
}

// Polls a job every 2.5s until it reaches a terminal state (completed/failed).
export function useJob(id: string | null, opts?: { poll?: boolean }) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => api.job(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      if (!opts?.poll) return false;
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 2500;
    },
  });
}

export function useGenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (brief: Record<string, unknown>) => api.generate(brief),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });
}

export function useVerify() {
  return useMutation({ mutationFn: (file: File) => api.verify(file) });
}
