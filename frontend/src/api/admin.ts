// Admin only: the logged-in user needs the admin role (python main.py make-admin <email>)
import { request } from "./client";
import type {
  EvaluationComparison, EvaluationRequest, EvaluationRun, EvaluationSummary, Job, JobFilters,
  LogEntry, LogFilters, Page, Stats, TraceDetail, TraceFilters, TraceSummary,
} from "./types";

export function getStats(hours = 24): Promise<Stats> {
  return request("/admin/stats", { query: { hours } });
}

export function listLogs(filters: LogFilters = {}): Promise<Page<LogEntry>> {
  return request("/admin/logs", { query: { ...filters } });
}

export function listTraces(filters: TraceFilters = {}): Promise<TraceSummary[]> {
  return request("/admin/traces", { query: { ...filters } });
}

export function getTrace(traceId: string): Promise<TraceDetail> {
  return request(`/admin/traces/${encodeURIComponent(traceId)}`);
}

/** Jobs of every user, evaluations included. */
export function listAllJobs(filters: JobFilters = {}): Promise<Page<Job>> {
  return request("/admin/jobs", { query: { ...filters } });
}

export function getAnyJob(jobId: string): Promise<Job> {
  return request(`/admin/jobs/${encodeURIComponent(jobId)}`);
}

export function listEvaluations(): Promise<EvaluationSummary[]> {
  return request("/admin/evaluations");
}

export function getEvaluation(tag: string): Promise<EvaluationRun> {
  return request(`/admin/evaluations/${encodeURIComponent(tag)}`);
}

export function compareEvaluations(a: string, b: string): Promise<EvaluationComparison> {
  return request("/admin/evaluations/compare", { query: { a, b } });
}

/** Runs in the worker; follow the returned job with getAnyJob. */
export function startEvaluation(body: EvaluationRequest): Promise<Job> {
  return request("/admin/evaluations", { body });
}
