import { request } from "./client";
import type { Job, JobFilters, JobStatus, Page } from "./types";

export function listJobs(filters: JobFilters = {}): Promise<Page<Job>> {
  return request("/jobs", { query: { ...filters } });
}

export function getJob(jobId: string): Promise<Job> {
  return request(`/jobs/${encodeURIComponent(jobId)}`);
}

export function isFinished(status: JobStatus): boolean {
  return status === "done" || status === "failed";
}
