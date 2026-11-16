import { useState } from "react";

import type { Source } from "../api/types";
import { pageLabel } from "../lib/format";
import { citeBadge, cx } from "./ui";

/** A passage of a document: a citation of an answer, or a search result. */
export function SourceCard({ source, id, highlighted = false }: { source: Source; id?: string; highlighted?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const where = [pageLabel(source), source.section].filter(Boolean).join(" · ");
  const score = source.score ?? source.embedding_score;
  return (
    <div id={id} className={cx("rounded-xl border bg-white p-3 text-sm transition-shadow dark:bg-zinc-900",
      highlighted ? "border-indigo-400 ring-4 ring-indigo-500/20" : "border-zinc-200 dark:border-zinc-800")}>
      <div className="flex items-start gap-2">
        <span className={cx(citeBadge, "mt-0.5")}>{source.number}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium" title={source.file_name ?? source.label}>{source.file_name ?? source.label}</p>
          <p className="truncate text-xs text-zinc-500 dark:text-zinc-400" title={where}>{where || " "}</p>
        </div>
        {score != null && (
          <span className="shrink-0 text-right" title={source.score_type === "rerank" || source.score != null
            ? "Relevance score from the reranker" : "Similarity score from the search"}>
            <span className="block text-xs font-medium tabular-nums">{score.toFixed(2)}</span>
            <span className="mt-1 block h-1 w-10 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <span className="block h-full rounded-full bg-indigo-500" style={{ width: `${Math.min(1, Math.max(0, score)) * 100}%` }} />
            </span>
          </span>
        )}
      </div>
      <p className={cx("mt-2 whitespace-pre-line text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-400", !expanded && "line-clamp-3")}>
        {source.text}
      </p>
      {source.text.length > 220 && (
        <button type="button" onClick={() => setExpanded(!expanded)} className="mt-1 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          {expanded ? "Show less" : "Show the whole passage"}
        </button>
      )}
    </div>
  );
}
