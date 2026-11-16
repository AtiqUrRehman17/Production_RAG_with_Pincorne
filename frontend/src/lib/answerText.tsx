// Turns an answer's text into React elements: paragraphs, lists, **bold**, headings
// and [n] citations as clickable chips. Only this small subset of Markdown is supported.
import type { ReactNode } from "react";

import { citeChip } from "../components/ui";

function inline(text: string, onCite: (n: number) => void, known: Set<number>, key: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\[\d+\])/g).filter(Boolean).map((part, i) => {
    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold) return <strong key={`${key}-${i}`} className="font-semibold text-zinc-900 dark:text-white">{bold[1]}</strong>;
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite && known.has(Number(cite[1]))) {
      const n = Number(cite[1]);
      return <button key={`${key}-${i}`} type="button" onClick={() => onCite(n)} className={citeChip} title={`Show source ${n}`}>{n}</button>;
    }
    return part;
  });
}

const LIST_ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/;

export function AnswerText({ text, citations, onCite }: {
  text: string;
  citations: number[]; // the source numbers that exist; other [n] stay plain text
  onCite: (n: number) => void;
}) {
  const known = new Set(citations);
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <>
      {blocks.map((block, b) => {
        const lines = block.split("\n").filter((line) => line.trim());
        if (lines.length && lines.every((line) => LIST_ITEM.test(line))) {
          const ordered = /^\s*\d/.test(lines[0]);
          const List = ordered ? "ol" : "ul";
          return (
            <List key={b} className={`${ordered ? "list-decimal" : "list-disc"} space-y-1 pl-5 marker:text-zinc-400`}>
              {lines.map((line, l) => <li key={l}>{inline(line.replace(LIST_ITEM, ""), onCite, known, `${b}-${l}`)}</li>)}
            </List>
          );
        }
        return (
          <p key={b}>
            {lines.map((line, l) => {
              const heading = line.match(/^#{1,6}\s+(.*)$/);
              const content = inline(heading ? heading[1] : line, onCite, known, `${b}-${l}`);
              return (
                <span key={l}>
                  {l > 0 && <br />}
                  {heading ? <strong className="font-semibold text-zinc-900 dark:text-white">{content}</strong> : content}
                </span>
              );
            })}
          </p>
        );
      })}
    </>
  );
}
