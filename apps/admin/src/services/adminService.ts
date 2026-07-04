// TanStack Query hooks for the admin console over the shared api client.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@veritas/shared";

export function useOverview(opts?: { poll?: number }) {
  return useQuery({
    queryKey: ["admin", "overview"],
    queryFn: api.adminOverview,
    refetchInterval: opts?.poll ?? false,
  });
}

export function useAdminLibrary(opts?: { poll?: number }) {
  return useQuery({
    queryKey: ["admin", "library"],
    queryFn: () => api.library().then((r) => r.jobs),
    refetchInterval: opts?.poll ?? false,
  });
}

export function useRetry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.retry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useRemove() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}
