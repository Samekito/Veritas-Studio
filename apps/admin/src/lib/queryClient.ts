import { QueryClient } from "@tanstack/react-query";

// Admin polls the ops overview frequently; keep retries low so an expired token
// surfaces (401) instead of being retried into a spin.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 2_000, retry: 0, refetchOnWindowFocus: false },
  },
});
