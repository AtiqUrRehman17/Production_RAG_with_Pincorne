import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { getReadiness } from "../../api/health";
import { PageHeader, Tabs } from "../../components/PageHeader";
import { badge, cx, tone } from "../../components/ui";
import { queryKeys } from "../../lib/queryKeys";
import { Evaluations } from "./Evaluations";
import { Jobs } from "./Jobs";
import { Logs } from "./Logs";
import { Overview } from "./Overview";
import { TraceDrawer } from "./TraceDrawer";
import { Traces } from "./Traces";

export type AdminTab = "overview" | "logs" | "traces" | "jobs" | "evals";
const TABS: { key: AdminTab; label: string }[] = [
  { key: "overview", label: "Overview" }, { key: "logs", label: "Logs" }, { key: "traces", label: "Traces" },
  { key: "jobs", label: "Jobs" }, { key: "evals", label: "Evaluations" },
];

/** Links between the tabs: a request ID opens its logs or traces, a trace ID opens the trace. */
export interface AdminLinks {
  showLogs: (requestId: string) => void;
  showTraces: (requestId: string) => void;
  openTrace: (traceId: string) => void;
}

// The tab, request-ID filter and open trace live in the URL (?tab=logs&rid=...&trace=...),
// so the back button works and chat answers can link straight to their trace
export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.key === params.get("tab")) ? params.get("tab") as AdminTab : "overview";
  const requestId = params.get("rid");
  const traceId = params.get("trace");
  const readiness = useQuery({ queryKey: queryKeys.readiness, queryFn: getReadiness, refetchInterval: 30_000 });

  const links: AdminLinks = {
    showLogs: (rid) => setParams(rid ? { tab: "logs", rid } : { tab: "logs" }),
    showTraces: (rid) => setParams({ tab: "traces", rid }),
    openTrace: (id) => setParams((current) => {
      const next = new URLSearchParams(current);
      next.set("trace", id);
      return next;
    }),
  };
  const clearRequestId = () => setParams({ tab });
  const closeTrace = () => setParams((current) => {
    const next = new URLSearchParams(current);
    next.delete("trace");
    return next;
  });

  const ready = readiness.data?.status === "ready";
  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
        <PageHeader title="Admin" subtitle="How the app is doing: usage, errors, AI traces and evaluations."
                    actions={readiness.isSuccess || readiness.isError ? (
                      <span className={cx(badge, "py-1 ring-1 ring-inset", ready ? `${tone.green} ring-emerald-200 dark:ring-emerald-500/30`
                                                                               : `${tone.red} ring-rose-200 dark:ring-rose-500/30`)}>
                        <span className={cx("size-1.5 rounded-full", ready ? "bg-emerald-500" : "bg-rose-500")} />
                        {ready ? "All systems ready" : readiness.isError ? "API unreachable" : "Something is not ready"}
                      </span>
                    ) : null} />
        <Tabs<AdminTab> items={TABS} active={tab} onChange={(key) => setParams({ tab: key })} />
        <div className="mt-6">
          {tab === "overview" && <Overview links={links} readiness={readiness} />}
          {tab === "logs" && <Logs links={links} requestId={requestId} onClearRequestId={clearRequestId} />}
          {tab === "traces" && <Traces links={links} requestId={requestId} onClearRequestId={clearRequestId} />}
          {tab === "jobs" && <Jobs />}
          {tab === "evals" && <Evaluations />}
        </div>
      </div>
      {traceId && <TraceDrawer traceId={traceId} links={links} onClose={closeTrace} />}
    </div>
  );
}
