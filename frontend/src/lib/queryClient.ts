import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // A 4xx won't change by asking again; network and server errors get two more tries
      retry: (failures, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500)
        && failures < 2,
    },
  },
});
