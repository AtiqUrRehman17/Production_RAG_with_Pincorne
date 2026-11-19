// Turns an answer's text into React elements: paragraphs, lists, **bold**, `code`, headings
// and [n] citations as interactive clickable chips.
import type { ReactNode } from "react";

import type { Source } from "../api/types";
import { citeChip } from "../components/ui";

function inline(
  text: string,
  onCite: (n: number) => void,
  known: Set<number>,
  sourcesMap: Map<number, Source>,
  key: string
): ReactNode[] {
  // Matches **bold**, `code`, and [n] citations
  return text
    .split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g)
    .filter(Boolean)
    .map((part, i) => {
      const bold = part.match(/^\*\*([^*]+)\*\*$/);
      if (bold) {
        return (
          <strong key={`${key}-${i}`} className="font-semibold text-slate-900 dark:text-white">
            {bold[1]}
          </strong>
        );
      }
      const code = part.match(/^`([^`]+)`$/);
      if (code) {
        return (
          <code
            key={`${key}-${i}`}
            className="rounded-md border border-slate-200/80 bg-slate-100 px-1.5 py-0.5 font-mono text-[13px] text-blue-600 dark:border-slate-800 dark:bg-slate-800/70 dark:text-blue-400"
          >
            {code[1]}
          </code>
        );
      }
      const cite = part.match(/^\[(\d+)\]$/);
      if (cite && known.has(Number(cite[1]))) {
        const n = Number(cite[1]);
        const src = sourcesMap.get(n);
        const tooltip = src
          ? `Source [${n}]: ${src.file_name ?? src.label}${src.page_number ? ` (p. ${src.page_number})` : ""} — Click to highlight`
          : `Show source [${n}]`;
        return (
          <button
            key={`${key}-${i}`}
            type="button"
            onClick={() => onCite(n)}
            className={`${citeChip} cursor-pointer shadow-2xs transition-transform active:scale-95`}
            title={tooltip}
          >
            {n}
          </button>
        );
      }
      return part;
    });
}

const LIST_ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/;

export function AnswerText({
  text,
  citations,
  sources = [],
  onCite,
}: {
  text: string;
  citations: number[];
  sources?: Source[];
  onCite: (n: number) => void;
}) {
  const known = new Set(citations);
  const sourcesMap = new Map<number, Source>(sources.map((s) => [s.number, s]));

  // Split into code blocks or paragraph blocks
  const blocks = text.trim().split(/\n{2,}/);

  return (
    <>
      {blocks.map((block, b) => {
        // Code block handling ```...```
        const codeBlock = block.match(/^```(\w+)?\n([\s\S]+?)```$/);
        if (codeBlock) {
          const lang = codeBlock[1];
          const content = codeBlock[2];
          return (
            <div
              key={b}
              className="my-3 overflow-hidden rounded-xl border border-slate-200 bg-slate-900 text-slate-100 dark:border-slate-800"
            >
              {lang && (
                <div className="border-b border-slate-800 bg-slate-950/60 px-3.5 py-1.5 text-[11px] font-mono text-slate-400">
                  {lang}
                </div>
              )}
              <pre className="scroll-thin overflow-x-auto p-3.5 text-xs font-mono leading-relaxed">
                <code>{content}</code>
              </pre>
            </div>
          );
        }

        const lines = block.split("\n").filter((line) => line.trim());

        if (lines.length && lines.every((line) => LIST_ITEM.test(line))) {
          const ordered = /^\s*\d/.test(lines[0]);
          const List = ordered ? "ol" : "ul";
          return (
            <List
              key={b}
              className={`${ordered ? "list-decimal" : "list-disc"} my-2 space-y-1.5 pl-5 marker:text-blue-500`}
            >
              {lines.map((line, l) => (
                <li key={l}>
                  {inline(line.replace(LIST_ITEM, ""), onCite, known, sourcesMap, `${b}-${l}`)}
                </li>
              ))}
            </List>
          );
        }

        return (
          <p key={b} className="my-2.5 leading-7">
            {lines.map((line, l) => {
              const heading = line.match(/^#{1,6}\s+(.*)$/);
              const content = inline(
                heading ? heading[1] : line,
                onCite,
                known,
                sourcesMap,
                `${b}-${l}`
              );
              return (
                <span key={l}>
                  {l > 0 && <br />}
                  {heading ? (
                    <strong className="mt-3 block text-base font-bold text-slate-900 dark:text-white">
                      {content}
                    </strong>
                  ) : (
                    content
                  )}
                </span>
              );
            })}
          </p>
        );
      })}
    </>
  );
}
