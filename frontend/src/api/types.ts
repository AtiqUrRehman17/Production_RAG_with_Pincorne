// The shapes the backend sends and receives (mirrors api/schemas/*.py).
// Dates arrive as ISO 8601 strings.

export interface ErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details: unknown;
  };
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null; // pass as cursor to get the next page; null = last page
}

export interface PageParams {
  limit?: number;
  cursor?: string | null;
}

// ---- accounts

export type Role = "user" | "admin";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number; // seconds
  user: User;
  transfer_job_id: string | null; // first account only
}

export interface RegisterRequest {
  email: string;
  password: string;
  name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ---- documents and jobs

export interface DocumentInfo {
  document_id: string;
  file_name: string;
  file_type: string;
  size_bytes: number;
  page_count: number | null;
  chunk_count: number;
  created_at: string;
}

export type JobType = "ingest" | "delete" | "evaluation" | "transfer";
export type JobStatus = "queued" | "processing" | "done" | "failed";

export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  file_name: string | null;
  document_id: string | null;
  progress: { step?: string; done?: number; total?: number } | null;
  result: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
  request_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobFilters extends PageParams {
  status?: JobStatus[];
  type?: JobType;
}

// ---- chat

export interface Conversation {
  id: string;
  title: string;
  document_ids: string[] | null; // null = all the user's documents
  created_at: string;
  updated_at: string;
}

export interface ConversationCreate {
  title?: string | null;
  document_ids?: string[] | null;
}

export interface ConversationUpdate {
  title?: string | null;
  document_ids?: string[] | null;
}

export interface Source {
  number: number;
  label: string; // e.g. "handbook.pdf, pages 4-6 (Leave Policy > Sick Leave)"
  document_id: string | null;
  file_name: string | null;
  page_number: number | null;
  page_end: number | null;
  section: string | null;
  text: string;
  score: number | null;
  embedding_score: number | null;
  score_type: string | null;
}

export type Rating = "up" | "down";

export interface Feedback {
  rating: Rating;
  comment: string | null;
  updated_at: string;
}

export interface FeedbackIn {
  rating: Rating;
  comment?: string | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "complete" | "error";
  found: boolean | null; // false: the documents don't answer the question
  searched_for: string | null; // the follow-up question rewritten to stand alone
  citations: Source[] | null;
  invalid_citations: number[] | null;
  error: string | null;
  trace_id: string | null;
  request_id: string | null;
  latency_ms: number | null;
  created_at: string;
  feedback: Feedback | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface AskRequest {
  question: string;
  no_rerank?: boolean;
}

export interface AskResponse {
  question: Message;
  answer: Message;
}

export interface SearchRequest {
  question: string;
  document_ids?: string[] | null;
  top_k?: number | null;
  no_rerank?: boolean;
}

export interface SearchResponse {
  question: string;
  ranking: string;
  passages: Source[];
}

// ---- health

export interface Health {
  status: string;
  version: string;
  time: string;
}

export interface Readiness {
  status: "ready" | "not_ready";
  checks: Record<string, { ok: boolean; detail: string | null }>;
  api_keys: Record<string, boolean>;
}

// ---- admin

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export interface LogEntry {
  id: number;
  created_at: string;
  level: LogLevel;
  logger: string;
  message: string;
  exception: string | null;
  request_id: string | null;
  source: "api" | "worker";
}

export interface LogFilters extends PageParams {
  level?: LogLevel;
  request_id?: string;
  q?: string;
  source?: "api" | "worker";
  since?: string;
  until?: string;
}

export interface TraceSummary {
  id: string;
  name: string;
  status: string | null;
  error: string | null;
  start_time: string;
  end_time: string | null;
  latency_seconds: number | null;
  total_tokens: number | null;
  tags: string[];
  request_id: string | null;
  conversation_id: string | null;
  question: string | null;
  url: string | null; // open the trace in LangSmith
}

export interface TraceStep {
  id: string;
  name: string;
  run_type: string;
  status: string | null;
  error: string | null;
  start_time: string;
  latency_seconds: number | null;
  total_tokens: number | null;
  inputs: unknown;
  outputs: unknown;
  steps: TraceStep[];
}

export interface TraceDetail extends TraceSummary {
  metadata: Record<string, unknown>;
  inputs: unknown;
  outputs: unknown;
  steps: TraceStep[];
}

export interface TraceFilters {
  errors_only?: boolean;
  min_seconds?: number;
  since?: string;
  conversation_id?: string;
  request_id?: string;
  limit?: number;
}

export interface Stats {
  hours: number;
  questions: {
    total: number;
    answered: number;
    not_found: number;
    errors: number;
    not_found_rate: number | null;
    avg_latency_ms: number | null;
    p95_latency_ms: number | null;
  };
  feedback: { up: number; down: number };
  jobs: Record<string, number>; // "<type>_<status>": count
  logs: { errors: number; warnings: number };
  recent_errors: LogEntry[];
}

export interface EvaluationRequest {
  saved_run?: string | null;
  retrieval_only?: boolean;
  no_rerank?: boolean;
  tag?: string | null;
  ids?: string[] | null;
  limit?: number | null;
  ragas?: boolean;
  ragas_metrics?: string[] | null;
  deepeval?: boolean;
  deepeval_metrics?: string[] | null;
}

export interface MetricValue {
  value: number;
  n: number; // how many questions it was measured on
}

export interface EvaluationSummary {
  tag: string;
  file: string;
  dataset: string;
  mode: string; // "full" | "retrieval"
  started_at: string;
  duration_seconds: number | null;
  questions: number;
  passed: MetricValue | null;
  judges: string[];
}

export interface EvaluationResult {
  id: string;
  question: string;
  type: string;
  answerable: boolean;
  passed: boolean | null;
  found?: boolean | null;
  seconds?: number | null;
  answer?: string | null;
  [key: string]: unknown;
}

// A saved run (evaluation/results/*.json); only the parts the app shows are typed
export interface EvaluationRun {
  tag: string;
  dataset: string;
  mode: string;
  started_at: string;
  duration_seconds: number | null;
  summary: Record<string, MetricValue | null>;
  results: EvaluationResult[];
  ragas?: { judge: string; summary: Record<string, MetricValue | null> } | null;
  deepeval?: { judge: string; summary: Record<string, MetricValue | null> } | null;
  [key: string]: unknown;
}

export interface ComparisonRow {
  name: string;
  label: string;
  a: string; // already formatted, "-" when not measured
  b: string;
  change: string; // e.g. "+0.050", "" when not comparable
}

export interface EvaluationComparison {
  a: { tag: string; mode: string; dataset: string; ranking: string; answers: string | null };
  b: { tag: string; mode: string; dataset: string; ranking: string; answers: string | null };
  same_dataset: boolean;
  metrics: ComparisonRow[];
  judges: { key: string; a: string | null; b: string | null; metrics: ComparisonRow[] }[];
  fixed: string[];
  broken: { id: string; type: string; question: string; reasons: string[] }[];
}
