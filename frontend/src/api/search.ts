import { request } from "./client";
import type { SearchRequest, SearchResponse } from "./types";

/** The passages most relevant to a question, without generating an answer. */
export function search(body: SearchRequest): Promise<SearchResponse> {
  return request("/search", { body });
}
