import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { compareEvaluations, getAnyJob, getEvaluation, listAllJobs, listEvaluations, startEvaluation } from "../../api/admin";
import { isFinished } from "../../api/jobs";
import type { ComparisonRow, EvaluationRequest, MetricValue } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { FullPageSpinner } from "../../components/FullPageSpinner";
import { Icon } from "../../components/Icon";
import { Drawer, Modal } from "../../components/Modal";
import { EmptyState } from "../../components/PageHeader";
import { badge, button, card, cx, field, label, tone } from "../../components/ui";
import { formatDateTime, formatRelative, formatSeconds, percent } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import { toast } from "../../lib/toast";

// Mirrors evaluation/metrics.py
const LABELS: Record<string, string> = {
  hit: "Hit rate", reciprocal_rank: "MRR", precision: "Precision", context_recall: "Context recall",
  correct_empty: "Correct empty (off-topic)", refusal_correct: "Refusal correct", key_facts: "Key facts found",
  all_key_facts: "All key facts found", citations_valid: "Citations valid", cites_expected: "Cites the right source",
  false_refusal: "False refusals", hallucination: "Hallucinations", passed: "Passed", errors: "Errors",
};
const COUNTS = new Set(["false_refusal", "hallucination", "passed", "errors"]);
const LOWER_IS_BETTER = new Set(["false_refusal", "hallucination", "errors"]);
const STEPS: Record<string, string> = { questions: "Answering the questions", ragas: "RAGAS judge grading", deepeval: "DeepEval judge grading" };

function showMetric(name: string, metric: MetricValue | null | undefined): string {
  if (!metric) return "–";
  if (COUNTS.has(name)) return `${metric.value} / ${metric.n}`;
  return name === "reciprocal_rank" ? metric.value.toFixed(3) : percent(metric.value, 1);
}

function passRate(passed: MetricValue | null): number | null {
  return passed && passed.n ? passed.value / passed.n : null;
}

export function Evaluations() {
  const queryClient = useQueryClient();
  const [starting, setStarting] = useState(false);
  const [startedJobId, setStartedJobId] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [compare, setCompare] = useState<string[]>([]);
  const [openTag, setOpenTag] = useState<string | null>(null);

  const runs = useQuery({ queryKey: queryKeys.admin.evaluations, queryFn: listEvaluations });
  // An evaluation started earlier (or by someone else) that is still running
  const active = useQuery({
    queryKey: queryKeys.admin.jobs({ type: "evaluation", status: ["queued", "processing"] }),
    queryFn: () => listAllJobs({ type: "evaluation", status: ["queued", "processing"], limit: 1 }),
  });
  const jobId = startedJobId ?? active.data?.items[0]?.id ?? null;
  const job = useQuery({
    queryKey: queryKeys.admin.job(jobId ?? ""),
    queryFn: () => getAnyJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && isFinished(q.state.data.status) ? false : 2000),
  });

  // Once the running evaluation finishes: say so and show the new run
  const announced = useRef<string | null>(null);
  useEffect(() => {
    const data = job.data;
    if (!data || !isFinished(data.status) || announced.current === data.id || !startedJobId) return;
    announced.current = data.id;
    void queryClient.invalidateQueries({ queryKey: queryKeys.admin.evaluations });
    if (data.status === "done") {
      const result = data.result as { tag?: string; passed?: MetricValue | null } | null;
      toast(`Evaluation “${result?.tag ?? ""}” finished${result?.passed ? `: ${result.passed.value} of ${result.passed.n} passed` : ""}.`);
    } else {
      toast(data.error ?? "The evaluation failed.", "error");
    }
  }, [job.data, startedJobId, queryClient]);

  const comparing = compare.length === 2 && compare[0] !== compare[1];
  const comparison = useQuery({
    queryKey: queryKeys.admin.comparison(compare[0] ?? "", compare[1] ?? ""),
    queryFn: () => compareEvaluations(compare[0], compare[1]),
    enabled: comparing,
  });

  const running = job.data && !isFinished(job.data.status);
  const progress = job.data?.progress;
  const showJob = job.data && job.data.id !== dismissed && (running || startedJobId === job.data.id);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500 dark:text-slate-400">Runs against the test questions. Tick two runs to compare them.</p>
        <button type="button" onClick={() => setStarting(true)} disabled={!!running} className={button("primary")}>
          <Icon name="play" className="size-4" /> Start evaluation
        </button>
      </div>

      {showJob && job.data && (
        <div className={cx(card, "fade-in p-4")}>
          {running ? (
            <>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium">{job.data.status === "queued" ? "Waiting for the worker" : STEPS[progress?.step ?? ""] ?? "Running"}</span>
                {progress?.total ? <span className="tabular-nums text-slate-500 dark:text-slate-400">{progress.done} / {progress.total}</span> : null}
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div className="stripes h-full rounded-full bg-blue-500 transition-all"
                     style={{ width: `${progress?.total ? Math.max(3, ((progress.done ?? 0) / progress.total) * 100) : 3}%` }} />
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Runs in the background worker; you can leave this page.</p>
            </>
          ) : (
            <div className="flex items-start gap-3 text-sm">
              <span className={cx("grid size-6 shrink-0 place-items-center rounded-full", job.data.status === "done" ? tone.green : tone.red)}>
                <Icon name={job.data.status === "done" ? "check" : "x"} className="size-3.5" />
              </span>
              <p className="flex-1">{job.data.status === "done" ? "The evaluation finished. Its run is in the list below." : job.data.error}</p>
              <button type="button" onClick={() => setDismissed(job.data!.id)} className="text-slate-400 hover:text-slate-700" aria-label="Dismiss">
                <Icon name="x" className="size-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {runs.isError && <ErrorMessage error={runs.error} />}
      {runs.isPending && <div className={cx(card, "space-y-2 p-4")}>{[1, 2, 3].map((i) => <div key={i} className="shimmer h-8 rounded" />)}</div>}
      {runs.isSuccess && !runs.data.length && <EmptyState title="No evaluation runs yet" text="Start one to measure how well the app answers." />}
      {runs.isSuccess && runs.data.length > 0 && (
        <div className={cx(card, "overflow-hidden")}>
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                <tr><th className="w-10 px-4 py-2.5"><span className="sr-only">Compare</span></th>
                  {["Run", "Mode", "Passed", "Judges", "Took", "When"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {runs.data.map((run) => {
                  const rate = passRate(run.passed);
                  return (
                    <tr key={run.file} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/30">
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={compare.includes(run.tag)} aria-label={`Compare ${run.tag}`} className="size-4 rounded accent-blue-600"
                               onChange={() => setCompare((tags) => (tags.includes(run.tag) ? tags.filter((t) => t !== run.tag) : [...tags, run.tag].slice(-2)))} />
                      </td>
                      <td className="px-4 py-3">
                        <button type="button" onClick={() => setOpenTag(run.tag)} className="font-mono text-xs font-medium text-blue-600 hover:underline dark:text-blue-400">{run.tag}</button>
                      </td>
                      <td className="px-4 py-3 text-slate-500 dark:text-slate-400">{run.mode === "retrieval" ? "Retrieval only" : "Full"}</td>
                      <td className="px-4 py-3">
                        {run.passed ? (
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                              <div className={cx("h-full rounded-full", rate! >= 0.85 ? "bg-emerald-500" : rate! >= 0.7 ? "bg-amber-400" : "bg-rose-500")}
                                   style={{ width: `${rate! * 100}%` }} />
                            </div>
                            <span className="tabular-nums">{run.passed.value}/{run.passed.n}</span>
                          </div>
                        ) : <span className="text-slate-400">–</span>}
                      </td>
                      <td className="px-4 py-3">
                        {run.judges.length ? run.judges.map((j) => <span key={j} className={cx(badge, tone.violet, "mr-1")}>{j === "ragas" ? "RAGAS" : "DeepEval"}</span>)
                                           : <span className="text-slate-400">–</span>}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-slate-500 dark:text-slate-400">{formatSeconds(run.duration_seconds)}</td>
                      <td className="px-4 py-3 text-slate-500 dark:text-slate-400" title={formatDateTime(run.started_at)}>{formatRelative(run.started_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {compare.length === 2 && !comparing && <p className="text-xs text-slate-500 dark:text-slate-400">Pick two runs with different names to compare them.</p>}
      {comparing && (
        <div className={cx(card, "fade-in p-5")}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Comparing <span className="font-mono">{compare[0]}</span> → <span className="font-mono">{compare[1]}</span></h3>
            <button type="button" onClick={() => setCompare([])} className={button("ghost", "sm")}>Clear</button>
          </div>
          {comparison.isPending && <div className="mt-4 space-y-2">{[1, 2, 3].map((i) => <div key={i} className="shimmer h-7 rounded" />)}</div>}
          {comparison.isError && <div className="mt-4"><ErrorMessage error={comparison.error} /></div>}
          {comparison.data && (
            <div className="mt-4 space-y-5">
              {!comparison.data.same_dataset && (
                <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
                  The runs used different question sets, so their scores are not comparable.
                </p>
              )}
              <CompareRows rows={comparison.data.metrics} />
              {comparison.data.judges.map((judge) => (
                <div key={judge.key}>
                  <p className="mb-1 text-xs font-semibold">{judge.key === "ragas" ? "RAGAS" : "DeepEval"} judge
                    <span className="font-normal text-slate-500 dark:text-slate-400"> · A: {judge.a ?? "not judged"} · B: {judge.b ?? "not judged"}</span></p>
                  <CompareRows rows={judge.metrics} />
                </div>
              ))}
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Questions that changed: <span className="font-medium text-emerald-600 dark:text-emerald-400">{comparison.data.fixed.length} now pass</span>
                {" · "}<span className="font-medium text-rose-600 dark:text-rose-400">{comparison.data.broken.length} now fail</span>
              </p>
              {comparison.data.broken.length > 0 && (
                <ul className="space-y-2">
                  {comparison.data.broken.map((item) => (
                    <li key={item.id} className="rounded-lg border border-rose-200 p-3 text-sm dark:border-rose-500/30">
                      <p><span className="font-mono text-xs text-slate-500">{item.id}</span> {item.question}</p>
                      <p className="mt-1 text-xs text-rose-700 dark:text-rose-300">{item.reasons.join(" · ")}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {starting && <StartDialog onClose={() => setStarting(false)} onStarted={(id) => {
        setStartedJobId(id);
        setStarting(false);
        toast("Evaluation started in the background.", "info");
      }} />}
      {openTag && <RunDrawer tag={openTag} onClose={() => setOpenTag(null)} />}
    </div>
  );
}

function CompareRows({ rows }: { rows: ComparisonRow[] }) {
  return (
    <div className="space-y-1">
      <div className="grid grid-cols-[1fr_4.5rem_4.5rem_4.5rem] gap-3 px-2 text-[11px] font-medium uppercase tracking-wider text-slate-400">
        <span>Metric</span><span className="text-right">A</span><span className="text-right">B</span><span className="text-right">Change</span>
      </div>
      {rows.map((row) => {
        const delta = parseFloat(row.change);
        const better = LOWER_IS_BETTER.has(row.name) ? delta < 0 : delta > 0;
        const color = !row.change || !delta ? "text-slate-400" : better ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400";
        return (
          <div key={row.name} className="grid grid-cols-[1fr_4.5rem_4.5rem_4.5rem] items-center gap-3 rounded-lg px-2 py-1.5 text-sm odd:bg-slate-50 dark:odd:bg-slate-800/40">
            <span className="min-w-0 truncate">{row.label}</span>
            <span className="text-right tabular-nums">{row.a}</span>
            <span className="text-right font-medium tabular-nums">{row.b}</span>
            <span className={cx("text-right text-xs font-medium tabular-nums", color)}>{row.change}</span>
          </div>
        );
      })}
    </div>
  );
}

function StartDialog({ onClose, onStarted }: { onClose: () => void; onStarted: (jobId: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body: EvaluationRequest = {
      retrieval_only: data.get("mode") === "retrieval",
      ragas: data.get("ragas") === "on",
      deepeval: data.get("deepeval") === "on",
      tag: String(data.get("tag")).trim() || null,
      limit: data.get("limit") === "all" ? null : Number(data.get("limit")),
    };
    setBusy(true);
    setError(null);
    try {
      onStarted((await startEvaluation(body)).id);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose} label="Start an evaluation" wide>
      <h2 className="font-semibold">Start an evaluation</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Asks the test questions and scores the results. It runs in the background.</p>
      <form onSubmit={submit} className="mt-5 space-y-4">
        <fieldset>
          <legend className={label}>What to test</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {[["full", "Full", "Search and answers"], ["retrieval", "Retrieval only", "Search only, no answer model calls"]].map(([value, title, text], i) => (
              <label key={value} className="flex cursor-pointer gap-3 rounded-xl border border-slate-200 p-3 has-[:checked]:border-blue-500
                                              has-[:checked]:bg-blue-50/50 dark:border-slate-700 dark:has-[:checked]:bg-blue-500/10">
                <input type="radio" name="mode" value={value} defaultChecked={i === 0} className="mt-0.5 accent-blue-600" />
                <span><span className="block text-sm font-medium">{title}</span><span className="block text-xs text-slate-500 dark:text-slate-400">{text}</span></span>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className={label}>AI judges <span className="font-normal text-slate-400">(slower, use the judge model's daily quota)</span></legend>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="ragas" className="size-4 rounded accent-blue-600" />RAGAS</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="deepeval" className="size-4 rounded accent-blue-600" />DeepEval</label>
          </div>
        </fieldset>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={label} htmlFor="eval-tag">Name <span className="font-normal text-slate-400">(optional)</span></label>
            <input id="eval-tag" name="tag" pattern="[A-Za-z0-9_\-]{1,40}" title="Letters, numbers, - and _ (up to 40)" placeholder="full" className={cx(field, "font-mono")} />
          </div>
          <div>
            <label className={label} htmlFor="eval-limit">Questions</label>
            <select id="eval-limit" name="limit" className={field} defaultValue="all">
              <option value="all">All</option><option value="5">First 5</option><option value="10">First 10</option>
            </select>
          </div>
        </div>
        <p className="flex gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
          <Icon name="info" className="size-4 shrink-0" /> A full run makes one answer call per question, and judges add more. Free tiers allow only a few full runs a day.
        </p>
        <ErrorMessage error={error} />
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className={button("secondary")}>Cancel</button>
          <button type="submit" disabled={busy} className={button("primary")}><Icon name="play" className="size-4" /> {busy ? "Starting…" : "Start"}</button>
        </div>
      </form>
    </Modal>
  );
}

function RunDrawer({ tag, onClose }: { tag: string; onClose: () => void }) {
  const query = useQuery({ queryKey: queryKeys.admin.evaluation(tag), queryFn: () => getEvaluation(tag) });
  const run = query.data;
  return (
    <Drawer onClose={onClose} label={`Evaluation ${tag}`} header={(
      <>
        <p className="font-mono text-xs text-slate-500 dark:text-slate-400">{run ? `${run.mode === "retrieval" ? "Retrieval only" : "Full"} · ${run.dataset}` : "Evaluation run"}</p>
        <h2 className="mt-1 font-semibold">{tag}</h2>
      </>
    )}>
      {query.isError && <ErrorMessage error={query.error} />}
      {query.isPending && <FullPageSpinner />}
      {run && (
        <>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.entries(run.summary).filter(([, metric]) => metric && metric.n).map(([name, metric]) => (
              <div key={name} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900">
                <dt className="truncate text-[11px] text-slate-500 dark:text-slate-400" title={LABELS[name] ?? name}>{LABELS[name] ?? name.replace(/_/g, " ")}</dt>
                <dd className="mt-0.5 text-sm font-semibold tabular-nums">{showMetric(name, metric)}</dd>
              </div>
            ))}
          </dl>
          {(["ragas", "deepeval"] as const).map((key) => run[key] && (
            <div key={key}>
              <p className="mb-2 text-sm font-semibold">{key === "ragas" ? "RAGAS" : "DeepEval"} <span className="font-normal text-slate-500 dark:text-slate-400">· {run[key]!.judge}</span></p>
              <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Object.entries(run[key]!.summary).filter(([, metric]) => metric).map(([name, metric]) => (
                  <div key={name} className="rounded-xl bg-sky-50/60 p-3 dark:bg-sky-500/10">
                    <dt className="truncate text-[11px] text-slate-500 dark:text-slate-400">{name.replace(/_/g, " ")}</dt>
                    <dd className="mt-0.5 text-sm font-semibold tabular-nums">{metric!.value.toFixed(3)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
          <div>
            <p className="mb-2 text-sm font-semibold">Questions <span className="font-normal text-slate-500 dark:text-slate-400">· {run.results.length}</span></p>
            <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
              {run.results.map((result) => (
                <li key={result.id} className="flex items-start gap-3 px-3 py-2.5 text-sm">
                  <span className={cx(badge, "mt-0.5 shrink-0", result.passed == null ? tone.gray : result.passed ? tone.green : tone.red)}>
                    {result.passed == null ? "n/a" : result.passed ? "pass" : "fail"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block">{result.question}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400"><span className="font-mono">{result.id}</span> · {result.type}
                      {result.seconds != null && ` · ${formatSeconds(result.seconds)}`}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </Drawer>
  );
}
