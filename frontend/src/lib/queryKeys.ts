// One place for cache keys, so a change (e.g. an upload finished) can refresh the right data.
// The chat list and one chat have separate roots: refreshing the list must not refetch (and so
// overwrite) a chat whose answer is still streaming in.
import type { JobFilters, LogFilters, TraceFilters } from "../api/types";

export const queryKeys = {
  documents: ["documents"] as const,
  jobs: (filters: JobFilters = {}) => ["jobs", filters] as const,
  job: (id: string) => ["job", id] as const,
  conversations: ["conversation-list"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  readiness: ["health", "ready"] as const,
  admin: {
    stats: (hours: number) => ["admin", "stats", hours] as const,
    logs: (filters: LogFilters) => ["admin", "logs", filters] as const,
    traces: (filters: TraceFilters) => ["admin", "traces", filters] as const,
    trace: (id: string) => ["admin", "trace", id] as const,
    jobs: (filters: JobFilters) => ["admin", "jobs", filters] as const,
    job: (id: string) => ["admin", "job", id] as const,
    evaluations: ["admin", "evaluations"] as const,
    evaluation: (tag: string) => ["admin", "evaluation", tag] as const,
    comparison: (a: string, b: string) => ["admin", "comparison", a, b] as const,
  },
};
