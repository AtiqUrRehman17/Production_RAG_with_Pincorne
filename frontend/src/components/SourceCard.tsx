import { useState } from "react";

import type { Source } from "../api/types";
import { fileType, pageLabel } from "../lib/format";
import { toast } from "../lib/toast";
import { Icon } from "./Icon";
import { citeBadge, cx } from "./ui";

/** A passage of a document: a citation of an answer, or a search result. */
export function SourceCard({
  source,
  id,
  highlighted = false,
}: {
  source: Source;
  id?: string;
  highlighted?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const where = [pageLabel(source), source.section].filter(Boolean).join(" · ");
  const rawScore = source.score ?? source.embedding_score;
  const isRerank = source.score_type === "rerank" || source.score != null;

  // Normalized visual percentage
  const scorePercent = rawScore != null ? Math.min(100, Math.max(0, Math.round(rawScore * 100))) : null;

  function copyPassage() {
    navigator.clipboard.writeText(source.text).then(
      () => toast("Passage text copied.", "info"),
      () => toast("Copy failed.", "error")
    );
  }

  const ext = fileType(source.file_name ?? source.label);

  return (
    <div
      id={id}
      className={cx(
        "group relative rounded-xl border bg-white p-3.5 text-sm shadow-xs transition-all duration-300 dark:bg-slate-900/90",
        highlighted
          ? "border-blue-500 ring-4 ring-blue-500/25 shadow-md shadow-blue-500/10 dark:border-blue-400 dark:ring-blue-400/20"
          : "border-slate-200/90 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700"
      )}
    >
      <div className="flex items-start justify-between gap-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cx(citeBadge, "font-mono font-bold")}>[{source.number}]</span>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                {ext}
              </span>
              <p
                className="truncate font-semibold text-slate-900 dark:text-slate-100"
                title={source.file_name ?? source.label}
              >
                {source.file_name ?? source.label}
              </p>
            </div>
            {where && (
              <p className="truncate text-xs text-slate-500 dark:text-slate-400" title={where}>
                {where}
              </p>
            )}
          </div>
        </div>

        {scorePercent != null && (
          <div
            className="shrink-0 text-right"
            title={
              isRerank
                ? `Relevance score: ${(rawScore ?? 0).toFixed(3)} (BGE-M3 cross-encoder reranker)`
                : `Similarity score: ${(rawScore ?? 0).toFixed(3)} (Gemini embedding cosine)`
            }
          >
            <div className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              <span
                className={cx(
                  "size-1.5 rounded-full",
                  scorePercent >= 70 ? "bg-emerald-500" : scorePercent >= 40 ? "bg-blue-500" : "bg-amber-500"
                )}
              />
              {scorePercent}% match
            </div>
          </div>
        )}
      </div>

      <div className="mt-2.5 rounded-lg bg-slate-50/70 p-2.5 text-slate-700 dark:bg-slate-950/50 dark:text-slate-300">
        <p
          className={cx(
            "whitespace-pre-line text-[13px] leading-relaxed",
            !expanded && "line-clamp-3"
          )}
        >
          {source.text}
        </p>
      </div>

      <div className="mt-2 flex items-center justify-between pt-1">
        {source.text.length > 200 ? (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline dark:text-blue-400 dark:hover:text-blue-300"
          >
            {expanded ? "Show less" : "Show full passage"}
          </button>
        ) : (
          <div />
        )}

        <button
          type="button"
          onClick={copyPassage}
          className="opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100 inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          title="Copy passage excerpt"
        >
          <Icon name="copy" className="size-3" />
          <span>Copy</span>
        </button>
      </div>
    </div>
  );
}
