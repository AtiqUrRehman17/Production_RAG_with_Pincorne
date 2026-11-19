import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listAllJobs } from "../../api/admin";
import { isFinished } from "../../api/jobs";
import type { Job, JobStatus, JobType } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { badge, button, card, cx, select, tone } from "../../components/ui";
import { formatDateTime, formatRelative, formatSeconds } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";

const STATUS_TONES: Record<JobStatus, string> = { done: tone.green, failed: tone.red, processing: tone.indigo, queued: tone.gray };

function took(job: Job): string {
  if (!job.started_at || !job.finished_at) return "–";
  return formatSeconds((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000);
}

function what(job: Job): string {
  if (job.file_name) return job.file_name;
  if (job.type === "evaluation") return `Evaluation${(job.result as { tag?: string } | null)?.tag ? ` “${(job.result as { tag: string }).tag}”` : ""}`;
  return job.document_id ?? "–";
}

export function Jobs() {
  const [status, setStatus] = useState<JobStatus | "">("");
  const [type, setType] = useState<JobType | "">("");
  const filters = { status: status ? [status] : undefined, type: type || undefined };
  const query = useInfiniteQuery({
    queryKey: queryKeys.admin.jobs(filters),
    queryFn: ({ pageParam }) => listAllJobs({ ...filters, limit: 30, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // Keep refreshing while something is still running
    refetchInterval: (q) => (q.state.data?.pages[0]?.items.some((job) => !isFinished(job.status)) ? 3000 : false),
  });
  const jobs = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select value={status} onChange={(event) => setStatus(event.target.value as JobStatus | "")} className={select} aria-label="Status">
          <option value="">Every status</option>
          {(["queued", "processing", "done", "failed"] as const).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={type} onChange={(event) => setType(event.target.value as JobType | "")} className={select} aria-label="Type">
          <option value="">Every type</option>
          {(["ingest", "delete", "evaluation", "transfer"] as const).map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      {query.isError && <ErrorMessage error={query.error} />}
      <div className={cx(card, "overflow-hidden")}>
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[44rem] text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              <tr>{["Job", "File", "Status", "Tries", "Took", "Created"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {jobs.map((job) => (
                <tr key={job.id} className="align-top hover:bg-slate-50/70 dark:hover:bg-slate-800/30">
                  <td className="px-4 py-3"><span className="font-medium capitalize">{job.type}</span>
                    <span className="block font-mono text-[11px] text-slate-500 dark:text-slate-400" title={job.id}>{job.id.slice(0, 8)}</span></td>
                  <td className="max-w-[18rem] px-4 py-3">
                    <span className="block truncate" title={what(job)}>{what(job)}</span>
                    {job.error && <span className="block text-xs text-rose-600 dark:text-rose-400">{job.error}</span>}
                    {job.progress?.total ? <span className="block text-xs text-slate-500 dark:text-slate-400">{job.progress.step} {job.progress.done}/{job.progress.total}</span> : null}
                  </td>
                  <td className="px-4 py-3"><span className={cx(badge, STATUS_TONES[job.status])}>{job.status}</span></td>
                  <td className="px-4 py-3 tabular-nums text-slate-500 dark:text-slate-400">{job.attempts}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-500 dark:text-slate-400">{took(job)}</td>
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400" title={formatDateTime(job.created_at)}>{formatRelative(job.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {query.isPending && <div className="space-y-2 p-4">{[1, 2, 3].map((i) => <div key={i} className="shimmer h-8 rounded" />)}</div>}
        {query.isSuccess && !jobs.length && <p className="px-6 py-12 text-center text-sm text-slate-500 dark:text-slate-400">No jobs match.</p>}
      </div>
      {query.hasNextPage && (
        <button type="button" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage} className={cx(button("secondary"), "w-full")}>
          {query.isFetchingNextPage ? "Loading…" : "Show older jobs"}
        </button>
      )}
    </div>
  );
}
