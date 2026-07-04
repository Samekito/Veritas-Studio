import { QueryClient } from "@tanstack/react-query";

// Single shared client. Short staleTime because generation state changes quickly;
// polling intervals are set per-query where needed.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false },
  },
});
