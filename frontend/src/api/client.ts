/**
 * Every call to the backend goes through here.
 *
 *   access token   kept only in memory (never localStorage, so injected scripts can't read it
 *                  later); sent as "Authorization: Bearer ..."
 *   refresh token  an HttpOnly cookie the browser sends to /api/v1/auth/* by itself
 *
 * When a call gets 401 (token expired, or none yet after a page reload), the client gets a new
 * access token from /auth/refresh once and repeats the call. If that fails too, the session is over.
 */
import type { ErrorBody, TokenResponse } from "./types";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number; // 0 = the server could not be reached
  readonly code: string; // e.g. "invalid_credentials", "file_too_large" (see the backend README)
  readonly requestId: string | null; // search the admin logs for this
  readonly details: unknown;
  readonly retryAfterSeconds: number | null; // set on 429 too_many_attempts

  constructor(status: number, code: string, message: string, requestId: string | null = null,
              details: unknown = null, retryAfterSeconds: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

type QueryValue = string | number | boolean | string[] | null | undefined;

export interface RequestOptions {
  method?: string;
  body?: unknown; // FormData is sent as is, anything else as JSON
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  auth?: boolean; // false: don't send the access token or refresh on 401 (login, register, refresh)
}

let accessToken: string | null = null;
let refreshing: Promise<TokenResponse> | null = null;
let sessionEnded: () => void = () => {};

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Called once the session can't be renewed (the AuthProvider logs the user out). */
export function onSessionEnded(handler: () => void): void {
  sessionEnded = handler;
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, String(item));
  }
  const search = params.toString();
  return `${API_BASE}${path}${search ? `?${search}` : ""}`;
}

function fallbackMessage(status: number): string {
  if (status === 0 || status === 502 || status === 503 || status === 504) {
    return "Can't reach the server. Check that the API is running (python -m api).";
  }
  if (status >= 500) return "Something went wrong on the server. Please try again.";
  return `The request failed (HTTP ${status}).`;
}

export async function toApiError(response: Response): Promise<ApiError> {
  let error: ErrorBody["error"] | undefined;
  try {
    error = ((await response.json()) as ErrorBody).error;
  } catch {
    // not JSON, e.g. the dev server could not reach the API
  }
  const retryAfter = Number(response.headers.get("Retry-After"));
  return new ApiError(
    response.status,
    error?.code ?? `http_${response.status}`,
    error?.message ?? fallbackMessage(response.status),
    error?.request_id ?? response.headers.get("X-Request-ID"),
    error?.details ?? null,
    Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
  );
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (options.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? (body === undefined ? "GET" : "POST"),
      headers,
      body,
      signal: options.signal,
      credentials: "include",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", fallbackMessage(0));
  }
}

/**
 * A new access token from the refresh cookie. Only one refresh runs at a time, also across
 * browser tabs: the refresh token is replaced on every use, and sending an already-used one
 * is treated as theft and ends the session.
 */
export function refreshSession(): Promise<TokenResponse> {
  refreshing ??= (async () => {
    const run = () => request<TokenResponse>("/auth/refresh", { method: "POST", auth: false });
    const tokens = navigator.locks ? await navigator.locks.request("rag-auth-refresh", run) : await run();
    accessToken = tokens.access_token;
    return tokens;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** The raw response of a successful call (for streams); throws ApiError otherwise. */
export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  let response = await send(path, options);
  if (response.status === 401 && options.auth !== false) {
    try {
      await refreshSession();
    } catch (error) {
      accessToken = null;
      sessionEnded();
      throw error instanceof ApiError ? error : await toApiError(response);
    }
    response = await send(path, options);
  }
  if (!response.ok) throw await toApiError(response);
  return response;
}

/** A call's JSON body (undefined for 204 No Content). */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiFetch(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
