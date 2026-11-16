import { API_BASE, ApiError, request, toApiError } from "./client";
import type { Health, Readiness } from "./types";

export function getHealth(): Promise<Health> {
  return request("/health", { auth: false });
}

/** Database, Redis, the worker and Pinecone; "not_ready" comes back as 503 with the same body. */
export async function getReadiness(): Promise<Readiness> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/health/ready`);
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the server. Check that the API is running (python -m api).");
  }
  if (response.ok || response.status === 503) {
    try {
      return (await response.json()) as Readiness;
    } catch {
      // the dev server's own 503 when the API is down: no JSON
    }
  }
  throw await toApiError(response);
}
