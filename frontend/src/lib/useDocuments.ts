import { useInfiniteQuery } from "@tanstack/react-query";

import { listDocuments } from "../api/documents";
import { queryKeys } from "./queryKeys";

/** All the user's documents (pages of 100, more loaded on request). */
export function useDocuments() {
  const query = useInfiniteQuery({
    queryKey: queryKeys.documents,
    queryFn: ({ pageParam }) => listDocuments({ limit: 100, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const documents = query.data?.pages.flatMap((page) => page.items) ?? [];
  return { ...query, documents };
}
