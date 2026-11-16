import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { getTrace } from "../../api/admin";
import type { TraceDetail, TraceStep } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { FullPageSpinner } from "../../components/FullPageSpinner";
import { Icon } from "../../components/Icon";
import { Drawer } from "../../components/Modal";
import { badge, button, cx, tone } from "../../components/ui";
import { formatRelative } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import type { AdminLinks } from "./AdminPage";

const TYPE_COLORS: Record<string, string> = {
  chain: "bg-violet-500", llm: "bg-indigo-500", retriever: "bg-emerald-500", embedding: "bg-sky-500", tool: "bg-amber-500",
  prompt: "bg-zinc-400", parser: "bg-zinc-400",
};
const MAX_JSON_CHARS = 20_000;

interface Row {
  id: string;
  name: string;
  type: string;
  depth: number;
  start: number; // seconds after the trace started
  seconds: number;
  error: string | null;
  inputs: unknown;
  outputs: unknown;
}

function rows(trace: TraceDetail): Row[] {
  const origin = new Date(trace.start_time).getTime();
  const out: Row[] = [{ id: trace.id, name: trace.name, type: "chain", depth: 0, start: 0, seconds: trace.latency_seconds ?? 0,
                        error: trace.error, inputs: trace.inputs, outputs: trace.outputs }];
  const walk = (steps: TraceStep[], depth: number) => steps.forEach((step) => {
    out.push({ id: step.id, name: step.name, type: step.run_type, depth, start: (new Date(step.start_time).getTime() - origin) / 1000,
               seconds: step.latency_seconds ?? 0, error: step.error, inputs: step.inputs, outputs: step.outputs });
    walk(step.steps, depth + 1);
  });
  walk(trace.steps, 1);
  return out;
}

function json(value: unknown): string {
  const text = JSON.stringify(value ?? null, null, 2) ?? "null";
  return text.length > MAX_JSON_CHARS ? `${text.slice(0, MAX_JSON_CHARS)}\n… (cut, see LangSmith for the rest)` : text;
}

export function TraceDrawer({ traceId, links, onClose }: { traceId: string; links: AdminLinks; onClose: () => void }) {
  const query = useQuery({ queryKey: queryKeys.admin.trace(traceId), queryFn: () => getTrace(traceId) });
  const [selected, setSelected] = useState<string | null>(null);
  const trace = query.data;

  const header = trace ? (
    <>
      <div className="flex items-center gap-2">
        <span className={cx(badge, trace.error ? tone.red : tone.green)}>{trace.error ? "Error" : "Success"}</span>
        <span className="truncate font-mono text-xs text-zinc-500 dark:text-zinc-400">{trace.id}</span>
      </div>
      <h2 className="mt-2 font-semibold leading-snug">{trace.question ?? trace.name}</h2>
    </>
  ) : <h2 className="font-semibold">Trace</h2>;

  if (!trace) {
    return (
      <Drawer onClose={onClose} label="Trace" header={header}>
        {query.isError ? <ErrorMessage error={query.error} /> : <FullPageSpinner />}
      </Drawer>
    );
  }

  const all = rows(trace);
  const total = Math.max(0.001, ...all.map((row) => row.start + row.seconds));
  const step = all.find((row) => row.id === selected);
  const facts: [string, ReactNode][] = [
    ["Total time", trace.latency_seconds != null ? `${trace.latency_seconds.toFixed(2)} s` : "running"],
    ["Tokens", trace.total_tokens?.toLocaleString() ?? "–"],
    ["Started", formatRelative(trace.start_time)],
    ["Request ID", trace.request_id ? (
      <button type="button" onClick={() => links.showLogs(trace.request_id!)} title="Show the logs of this request"
              className="font-mono text-indigo-600 hover:underline dark:text-indigo-400">{trace.request_id}</button>
    ) : "–"],
  ];

  return (
    <Drawer onClose={onClose} label="Trace" header={header}>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {facts.map(([name, value]) => (
          <div key={name} className="min-w-0 rounded-xl bg-zinc-50 p-3 dark:bg-zinc-900">
            <dt className="text-[11px] text-zinc-500 dark:text-zinc-400">{name}</dt>
            <dd className="mt-0.5 truncate text-sm font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      {trace.error && <pre className="scroll-thin overflow-x-auto whitespace-pre-wrap rounded-xl bg-rose-50 p-3 font-mono text-xs text-rose-800 dark:bg-rose-500/10 dark:text-rose-200">{trace.error}</pre>}

      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Steps</h3>
          <span className="text-[11px] text-zinc-500 dark:text-zinc-400">click a step to see its input and output</span>
        </div>
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800">
          {all.map((row) => (
            <button key={row.id} type="button" onClick={() => setSelected(selected === row.id ? null : row.id)}
                    className={cx("grid w-full grid-cols-[minmax(0,11rem)_1fr_3.5rem] items-center gap-3 border-b border-zinc-100 px-3 py-2 text-left",
                                  "last:border-0 hover:bg-zinc-50 sm:grid-cols-[minmax(0,14rem)_1fr_4rem] dark:border-zinc-800 dark:hover:bg-zinc-800/40",
                                  selected === row.id && "bg-indigo-50/60 dark:bg-indigo-500/10")}>
              <span className="flex min-w-0 items-center gap-2" style={{ paddingLeft: row.depth * 14 }}>
                <span className={cx("size-2 shrink-0 rounded-sm", row.error ? "bg-rose-500" : TYPE_COLORS[row.type] ?? "bg-zinc-400")} />
                <span className={cx("truncate font-mono text-xs", row.error && "text-rose-600 dark:text-rose-400")} title={row.name}>{row.name}</span>
              </span>
              <span className="relative h-4 rounded bg-zinc-100 dark:bg-zinc-800/60">
                <span className={cx("absolute inset-y-0 rounded opacity-80", row.error ? "bg-rose-500" : TYPE_COLORS[row.type] ?? "bg-zinc-400")}
                      style={{ left: `${(row.start / total) * 100}%`, width: `${Math.max(1, (row.seconds / total) * 100)}%` }} />
              </span>
              <span className="text-right font-mono text-[11px] tabular-nums text-zinc-500 dark:text-zinc-400">{row.seconds.toFixed(2)}s</span>
            </button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-zinc-500 dark:text-zinc-400">
          {["chain", "llm", "retriever", "embedding", "tool"].map((type) => (
            <span key={type} className="flex items-center gap-1.5"><span className={cx("size-2 rounded-sm", TYPE_COLORS[type])} />{type}</span>
          ))}
        </div>
      </div>

      {step && (
        <div className="fade-in grid gap-3 sm:grid-cols-2">
          {([["Input", step.inputs], ["Output", step.outputs]] as const).map(([name, value]) => (
            <div key={name} className="min-w-0">
              <p className="mb-1.5 text-xs font-semibold">{name} · <span className="font-mono font-normal text-zinc-500 dark:text-zinc-400">{step.name}</span></p>
              <pre className="scroll-thin max-h-96 overflow-auto rounded-xl bg-zinc-900 p-3 font-mono text-[11px] leading-relaxed text-zinc-100 dark:bg-black">{json(value)}</pre>
            </div>
          ))}
        </div>
      )}

      {trace.url && (
        <a href={trace.url} target="_blank" rel="noreferrer" className={cx(button("secondary"), "w-full")}>
          <Icon name="external" className="size-4" /> Open this trace in LangSmith
        </a>
      )}
    </Drawer>
  );
}
