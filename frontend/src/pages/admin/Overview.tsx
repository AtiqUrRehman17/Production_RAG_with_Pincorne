import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { getStats } from "../../api/admin";
import type { Readiness } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Icon } from "../../components/Icon";
import { badge, card, cx, link, select, tone } from "../../components/ui";
import { formatRelative, percent } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import type { AdminLinks } from "./AdminPage";

const PERIODS = [[24, "Last 24 hours"], [168, "Last 7 days"], [720, "Last 30 days"]] as const;
const JOB_TYPES: Record<string, string> = { ingest: "Uploads", delete: "Deletes", evaluation: "Evaluations", transfer: "Transfers" };

function Stat({ title, value, sub, valueClass, children }: { title: string; value: string; sub: string; valueClass?: string; children?: ReactNode }) {
  return (
    <div className={cx(card, "p-4 sm:p-5")}>
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{title}</p>
      <p className={cx("mt-1.5 text-2xl font-semibold tracking-tight tabular-nums", valueClass)}>{value}</p>
      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{sub}</p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export function Overview({ links, readiness }: { links: AdminLinks; readiness: UseQueryResult<Readiness> }) {
  const [hours, setHours] = useState(24);
  const stats = useQuery({ queryKey: queryKeys.admin.stats(hours), queryFn: () => getStats(hours), refetchInterval: 60_000 });

  const period = (
    <select value={hours} onChange={(event) => setHours(Number(event.target.value))} className={cx(select, "py-1.5 text-xs")} aria-label="Period">
      {PERIODS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
    </select>
  );

  if (stats.isPending) {
    return <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[1, 2, 3, 4].map((i) => <div key={i} className={cx(card, "shimmer h-36")} />)}</div>;
  }
  if (stats.isError) return <ErrorMessage error={stats.error} />;

  const { questions: q, feedback, jobs, logs, recent_errors: errors } = stats.data;
  const rated = feedback.up + feedback.down;
  const answered = q.answered, notFound = q.not_found, failed = q.errors;
  const total = Math.max(1, answered + notFound + failed);
  const jobRows = Object.entries(jobs).map(([key, count]) => {
    const [type, status] = key.split("_");
    return { type: JOB_TYPES[type] ?? type, status, count };
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">{period}</div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <Stat title="Questions" value={String(q.total)} sub={`${answered} answered · ${failed} failed`} />
        <Stat title="Not found" value={percent(q.not_found_rate, 1)} sub={`${notFound} had no answer in the documents`}
              valueClass={q.not_found_rate != null && q.not_found_rate > 0.2 ? "text-amber-600 dark:text-amber-400" : undefined} />
        <Stat title="Answer time" value={q.avg_latency_ms != null ? `${(q.avg_latency_ms / 1000).toFixed(1)} s` : "–"}
              sub={q.p95_latency_ms != null ? `average · 95% under ${(q.p95_latency_ms / 1000).toFixed(1)} s` : "no answers yet"} />
        <Stat title="Feedback" value={rated ? percent(feedback.up / rated) : "–"} sub={`${feedback.up} good · ${feedback.down} bad`}
              valueClass={rated ? "text-emerald-600 dark:text-emerald-400" : undefined}>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            {rated > 0 && <><span className="bg-emerald-500" style={{ width: `${(feedback.up / rated) * 100}%` }} />
                            <span className="bg-rose-400" style={{ width: `${(feedback.down / rated) * 100}%` }} /></>}
          </div>
        </Stat>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className={cx(card, "p-5 lg:col-span-2")}>
          <h3 className="text-sm font-semibold">How questions were answered</h3>
          {q.total ? (
            <>
              <div className="mt-5 flex h-4 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <span className="bg-blue-500" style={{ width: `${(answered / total) * 100}%` }} />
                <span className="bg-amber-400" style={{ width: `${(notFound / total) * 100}%` }} />
                <span className="bg-rose-500" style={{ width: `${(failed / total) * 100}%` }} />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                {[["Answered", answered, "bg-blue-500"], ["Not found", notFound, "bg-amber-400"], ["Failed", failed, "bg-rose-500"]].map(([name, count, color]) => (
                  <div key={name as string}>
                    <p className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400"><span className={cx("size-2 rounded-sm", color as string)} />{name}</p>
                    <p className="mt-0.5 text-lg font-semibold tabular-nums">{count}</p>
                  </div>
                ))}
              </div>
            </>
          ) : <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">No questions in this period.</p>}
          <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4 text-xs dark:border-slate-800">
            <button type="button" onClick={() => links.showLogs("")} className={cx(badge, logs.errors ? tone.red : tone.gray)}>{logs.errors} errors logged</button>
            <span className={cx(badge, logs.warnings ? tone.amber : tone.gray)}>{logs.warnings} warnings</span>
          </div>
        </div>

        <div className={cx(card, "p-5")}>
          <h3 className="text-sm font-semibold">System</h3>
          {readiness.isPending && <div className="mt-3 space-y-3">{[1, 2, 3, 4].map((i) => <div key={i} className="shimmer h-7 rounded-lg" />)}</div>}
          {readiness.isError && <div className="mt-3"><ErrorMessage error={readiness.error} /></div>}
          {readiness.data && (
            <>
              <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
                {Object.entries(readiness.data.checks).map(([name, check]) => (
                  <li key={name} className="flex items-center gap-3 py-2.5">
                    <span className={cx("grid size-6 shrink-0 place-items-center rounded-full", check.ok ? tone.green : tone.red)}>
                      <Icon name={check.ok ? "check" : "x"} className="size-3.5" />
                    </span>
                    <span className="flex-1 text-sm font-medium capitalize">{name}</span>
                    {check.detail && <span className="max-w-[55%] truncate text-xs text-slate-500 dark:text-slate-400" title={check.detail}>{check.detail}</span>}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                API keys set: {Object.entries(readiness.data.api_keys).filter(([, set]) => set).map(([name]) => name).join(", ") || "none"}
                {Object.values(readiness.data.api_keys).some((set) => !set) && (
                  <span className="text-amber-600 dark:text-amber-400"> · missing: {Object.entries(readiness.data.api_keys).filter(([, set]) => !set).map(([name]) => name).join(", ")}</span>
                )}
              </p>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className={cx(card, "p-5")}>
          <h3 className="text-sm font-semibold">Background jobs</h3>
          {jobRows.length ? (
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {jobRows.map((row) => (
                <div key={`${row.type}-${row.status}`} className="rounded-xl bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                  <p className={cx("text-xl font-semibold tabular-nums", row.status === "failed" ? "text-rose-600 dark:text-rose-400"
                                                                       : row.status === "done" ? "text-emerald-600 dark:text-emerald-400" : "")}>{row.count}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{row.type} {row.status}</p>
                </div>
              ))}
            </div>
          ) : <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">No background jobs in this period.</p>}
        </div>

        <div className={cx(card, "p-5")}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Recent errors</h3>
            <button type="button" onClick={() => links.showLogs("")} className={cx(link, "text-xs")}>All logs</button>
          </div>
          {errors.length ? (
            <ul className="mt-3 space-y-1">
              {errors.map((entry) => (
                <li key={entry.id}>
                  <button type="button" onClick={() => entry.request_id && links.showLogs(entry.request_id)}
                          className="flex w-full items-start gap-2.5 rounded-lg p-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <span className={cx(badge, tone.red, "shrink-0")}>{entry.level}</span>
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-1 text-sm">{entry.message}</span>
                      <span className="text-[11px] text-slate-500 dark:text-slate-400">{entry.source} · {formatRelative(entry.created_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : <p className="mt-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400"><Icon name="check" className="size-4 text-emerald-500" />No errors in this period.</p>}
        </div>
      </div>
    </div>
  );
}
