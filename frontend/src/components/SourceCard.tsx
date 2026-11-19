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
        "group relative rounded-xl border bg-white p-3.5 text-sm shadow-xs transition-all duration-300 dark:bg-zinc-900/90",
        highlighted
          ? "border-indigo-500 ring-4 ring-indigo-500/25 shadow-md shadow-indigo-500/10 dark:border-indigo-400 dark:ring-indigo-400/20"
          : "border-zinc-200/90 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700"
      )}
    >
      <div className="flex items-start justify-between gap-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cx(citeBadge, "font-mono font-bold")}>[{source.number}]</span>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                {ext}
              </span>
              <p
                className="truncate font-semibold text-zinc-900 dark:text-zinc-100"
                title={source.file_name ?? source.label}
              >
                {source.file_name ?? source.label}
              </p>
            </div>
            {where && (
              <p className="truncate text-xs text-zinc-500 dark:text-zinc-400" title={where}>
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
            <div className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              <span
                className={cx(
                  "size-1.5 rounded-full",
                  scorePercent >= 70 ? "bg-emerald-500" : scorePercent >= 40 ? "bg-indigo-500" : "bg-amber-500"
                )}
              />
              {scorePercent}% match
            </div>
          </div>
        )}
      </div>

      <div className="mt-2.5 rounded-lg bg-zinc-50/70 p-2.5 text-zinc-700 dark:bg-zinc-950/50 dark:text-zinc-300">
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
            className="text-xs font-medium text-indigo-600 hover:text-indigo-700 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300"
          >
            {expanded ? "Show less" : "Show full passage"}
          </button>
        ) : (
          <div />
        )}

        <button
          type="button"
          onClick={copyPassage}
          className="opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100 inline-flex items-center gap-1 text-[11px] font-medium text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
          title="Copy passage excerpt"
        >
          <Icon name="copy" className="size-3" />
          <span>Copy</span>
        </button>
      </div>
    </div>
  );
}
