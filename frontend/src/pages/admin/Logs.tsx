import { useInfiniteQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";

import { listLogs } from "../../api/admin";
import type { LogEntry, LogLevel } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Icon } from "../../components/Icon";
import { badge, button, card, cx, fieldBase, select, tone } from "../../components/ui";
import { formatClock, formatDateTime } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import type { AdminLinks } from "./AdminPage";

const LEVELS: LogLevel[] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const LEVEL_COLORS: Record<LogLevel, string> = {
  DEBUG: "text-zinc-400", INFO: "text-sky-600 dark:text-sky-400", WARNING: "text-amber-600 dark:text-amber-400",
  ERROR: "text-rose-600 dark:text-rose-400", CRITICAL: "text-rose-700 dark:text-rose-300",
};
const GRID = "grid-cols-[4.5rem_4.5rem_1fr] sm:grid-cols-[5.5rem_4.5rem_4rem_1fr_7.5rem]";

export function Logs({ links, requestId, onClearRequestId }: { links: AdminLinks; requestId: string | null; onClearRequestId: () => void }) {
  const [text, setText] = useState("");
  const [level, setLevel] = useState<LogLevel>(requestId ? "DEBUG" : "INFO");
  const [source, setSource] = useState<"" | "api" | "worker">("");
  const [open, setOpen] = useState<number | null>(null);
  const q = useDeferredValue(text.trim());

  const filters = { level, q: q || undefined, source: source || undefined, request_id: requestId || undefined };
  const query = useInfiniteQuery({
    queryKey: queryKeys.admin.logs(filters),
    queryFn: ({ pageParam }) => listLogs({ ...filters, limit: 50, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const entries = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <div className="relative min-w-[12rem] flex-1">
          <span className="pointer-events-none absolute inset-y-0 left-3 grid place-items-center text-zinc-400"><Icon name="search" className="size-4" /></span>
          <input value={text} onChange={(event) => setText(event.target.value)} maxLength={200} placeholder="Search messages"
                 aria-label="Search messages" className={cx(fieldBase, "py-2 pl-9 pr-3")} />
        </div>
        <select value={level} onChange={(event) => setLevel(event.target.value as LogLevel)} className={select} aria-label="Lowest level">
          {LEVELS.map((l) => <option key={l} value={l}>{l} and up</option>)}
        </select>
        <select value={source} onChange={(event) => setSource(event.target.value as typeof source)} className={select} aria-label="Source">
          <option value="">API and worker</option><option value="api">API only</option><option value="worker">Worker only</option>
        </select>
        <button type="button" onClick={() => void query.refetch()} className={button("secondary")} title="Refresh" aria-label="Refresh">
          <Icon name="refresh" className={cx("size-4", query.isRefetching && "animate-spin")} />
        </button>
      </div>
      {requestId && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400">Showing request</span>
          <span className={cx(badge, tone.indigo, "font-mono")}>
            {requestId}
            <button type="button" onClick={onClearRequestId} className="ml-1 hover:opacity-70" aria-label="Show all requests"><Icon name="x" className="size-3" /></button>
          </span>
          <button type="button" onClick={() => links.showTraces(requestId)} className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">Its traces</button>
        </div>
      )}

      <div className={cx(card, "overflow-hidden")}>
        <div className={cx("hidden gap-3 border-b border-zinc-200 bg-zinc-50 px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-zinc-500 sm:grid",
                           "dark:border-zinc-800 dark:bg-zinc-900", GRID)}>
          <span>Time</span><span>Level</span><span>Source</span><span>Message</span><span>Request ID</span>
        </div>
        {query.isPending && <div className="space-y-2 p-4">{[1, 2, 3, 4].map((i) => <div key={i} className="shimmer h-6 rounded" />)}</div>}
        {query.isError && <div className="p-4"><ErrorMessage error={query.error} /></div>}
        {query.isSuccess && !entries.length && <p className="px-6 py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">No logs match these filters.</p>}
        {entries.map((entry) => (
          <LogRow key={entry.id} entry={entry} open={open === entry.id} onToggle={() => setOpen(open === entry.id ? null : entry.id)} links={links} />
        ))}
      </div>
      {query.hasNextPage && (
        <button type="button" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage} className={cx(button("secondary"), "w-full")}>
          {query.isFetchingNextPage ? "Loading…" : "Show older logs"}
        </button>
      )}
    </div>
  );
}

function LogRow({ entry, open, onToggle, links }: { entry: LogEntry; open: boolean; onToggle: () => void; links: AdminLinks }) {
  const serious = entry.level === "ERROR" || entry.level === "CRITICAL";
  return (
    <div className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
      <button type="button" onClick={onToggle} aria-expanded={open}
              className={cx("grid w-full items-baseline gap-3 px-4 py-2.5 text-left font-mono text-xs hover:bg-zinc-50 dark:hover:bg-zinc-800/40", GRID,
                            serious && "bg-rose-50/40 dark:bg-rose-500/5")}>
        <span className="text-zinc-400">{formatClock(entry.created_at)}</span>
        <span className={cx("font-semibold", LEVEL_COLORS[entry.level])}>{entry.level}</span>
        <span className="hidden text-zinc-500 sm:block">{entry.source}</span>
        <span className="min-w-0 truncate font-sans text-[13px] text-zinc-800 dark:text-zinc-200">{entry.message}</span>
        <span className="hidden truncate text-indigo-600 sm:block dark:text-indigo-400">{entry.request_id ?? ""}</span>
      </button>
      {open && (
        <div className="fade-in space-y-3 bg-zinc-50 px-4 py-3 text-xs dark:bg-zinc-900">
          <p className="whitespace-pre-wrap wrap-break-word text-[13px] text-zinc-800 dark:text-zinc-200">{entry.message}</p>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div><dt className="text-zinc-500 dark:text-zinc-400">Time</dt><dd className="font-mono">{formatDateTime(entry.created_at)}</dd></div>
            <div><dt className="text-zinc-500 dark:text-zinc-400">Source</dt><dd className="font-mono">{entry.source}</dd></div>
            <div className="min-w-0"><dt className="text-zinc-500 dark:text-zinc-400">Logger</dt><dd className="truncate font-mono" title={entry.logger}>{entry.logger}</dd></div>
            <div className="min-w-0">
              <dt className="text-zinc-500 dark:text-zinc-400">Request ID</dt>
              <dd>{entry.request_id ? (
                <button type="button" onClick={() => links.showLogs(entry.request_id!)} title="Every log of this request"
                        className="truncate font-mono text-indigo-600 hover:underline dark:text-indigo-400">{entry.request_id}</button>
              ) : "–"}</dd>
            </div>
          </dl>
          {entry.exception && (
            <pre className="scroll-thin overflow-x-auto rounded-lg bg-zinc-900 p-3 font-mono text-[11px] leading-relaxed text-zinc-100 dark:bg-black">{entry.exception}</pre>
          )}
          {entry.request_id && (
            <button type="button" onClick={() => links.showTraces(entry.request_id!)} className={button("secondary", "sm")}>
              <Icon name="list" className="size-3.5" /> Find the trace of this request
            </button>
          )}
        </div>
      )}
    </div>
  );
}
