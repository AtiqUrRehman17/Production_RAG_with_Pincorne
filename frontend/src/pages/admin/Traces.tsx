import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listTraces } from "../../api/admin";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Icon } from "../../components/Icon";
import { badge, card, cx, tone } from "../../components/ui";
import { formatRelative } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import type { AdminLinks } from "./AdminPage";

const SLOW_SECONDS = 5;

export function Traces({ links, requestId, onClearRequestId }: { links: AdminLinks; requestId: string | null; onClearRequestId: () => void }) {
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [slowOnly, setSlowOnly] = useState(false);
  const filters = { errors_only: errorsOnly || undefined, min_seconds: slowOnly ? SLOW_SECONDS : undefined,
                    request_id: requestId || undefined, limit: 30 };
  const query = useQuery({ queryKey: queryKeys.admin.traces(filters), queryFn: () => listTraces(filters) });

  const toggle = (on: boolean, set: (value: boolean) => void, text: string) => (
    <button type="button" onClick={() => set(!on)} aria-pressed={on}
            className={cx(badge, "cursor-pointer px-3 py-1.5 ring-1 ring-inset", on ? "bg-indigo-600 text-white ring-indigo-600"
              : "bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700")}>
      {text}
    </button>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {toggle(errorsOnly, setErrorsOnly, "Errors only")}
        {toggle(slowOnly, setSlowOnly, `Slower than ${SLOW_SECONDS} s`)}
        {requestId && (
          <span className={cx(badge, tone.indigo, "py-1.5 font-mono")}>
            {requestId}
            <button type="button" onClick={onClearRequestId} className="ml-1 hover:opacity-70" aria-label="Show all traces"><Icon name="x" className="size-3" /></button>
          </span>
        )}
        <span className="ml-auto text-xs text-zinc-500 dark:text-zinc-400">Last 7 days, from LangSmith</span>
      </div>
      {query.isError && <ErrorMessage error={query.error} />}
      <div className={cx(card, "divide-y divide-zinc-100 overflow-hidden dark:divide-zinc-800")}>
        {query.isPending && <div className="space-y-3 p-4">{[1, 2, 3, 4].map((i) => <div key={i} className="shimmer h-10 rounded" />)}</div>}
        {query.isSuccess && !query.data.length && <p className="px-6 py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">No traces match.</p>}
        {query.data?.map((trace) => (
          <button key={trace.id} type="button" onClick={() => links.openTrace(trace.id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
            <span className={cx("size-2 shrink-0 rounded-full", trace.error ? "bg-rose-500" : trace.end_time ? "bg-emerald-500" : "bg-amber-400")} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{trace.question ?? trace.name}</span>
              <span className="block truncate text-xs text-zinc-500 dark:text-zinc-400">
                {trace.error && <span className="text-rose-600 dark:text-rose-400">{trace.error.split("\n")[0]} · </span>}
                {formatRelative(trace.start_time)} · <span className="font-mono">{trace.id}</span>
              </span>
            </span>
            <span className="hidden w-24 text-right sm:block">
              <span className={cx("block text-sm tabular-nums", (trace.latency_seconds ?? 0) > SLOW_SECONDS && "text-amber-600 dark:text-amber-400")}>
                {trace.latency_seconds != null ? `${trace.latency_seconds.toFixed(2)} s` : "running"}
              </span>
              <span className="block text-[11px] text-zinc-500 dark:text-zinc-400">{trace.total_tokens != null ? `${trace.total_tokens.toLocaleString()} tokens` : ""}</span>
            </span>
            <Icon name="chevron" className="size-4 shrink-0 text-zinc-400" />
          </button>
        ))}
      </div>
    </div>
  );
}
