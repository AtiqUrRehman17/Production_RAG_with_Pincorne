import { Link } from "react-router";

import type { DocumentInfo } from "../../api/types";
import { Icon } from "../../components/Icon";
import { Logo } from "../../components/Logo";
import { button } from "../../components/ui";

const PROMPTS = [
  (name: string) => `Summarize ${name}`,
  (name: string) => `What are the most important points in ${name}?`,
  (name: string) => `What does ${name} say about deadlines or dates?`,
  (name: string) => `List the rules or requirements in ${name}`,
];

/** A new chat: suggested questions about the documents it searches, or an upload prompt. */
export function EmptyChat({ documents, onAsk }: { documents: DocumentInfo[]; onAsk: (question: string) => void }) {
  if (!documents.length) {
    return (
      <div className="grid h-full place-items-center px-4">
        <div className="fade-in max-w-md text-center">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300">
            <Icon name="upload" className="size-7" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">Upload a document to get started</h2>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Add a PDF, Word file or text file. Once it's processed you can ask questions about it here.
          </p>
          <Link to="/documents" className={`${button("primary")} mt-6`}><Icon name="upload" className="size-4" /> Upload documents</Link>
        </div>
      </div>
    );
  }

  const suggestions = PROMPTS.map((prompt, i) => {
    const doc = documents[i % documents.length];
    return { question: prompt(doc.file_name), file: doc.file_name };
  }).slice(0, documents.length === 1 ? 2 : 4);

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="fade-in w-full max-w-2xl text-center">
        <div className="mx-auto w-fit"><Logo size="lg" /></div>
        <h2 className="mt-5 text-2xl font-semibold tracking-tight">What would you like to know?</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500 dark:text-zinc-400">
          Answers come only from your documents, with numbered citations you can open and check.
        </p>
        <div className="mt-8 grid gap-2.5 text-left sm:grid-cols-2">
          {suggestions.map((s) => (
            <button key={s.question} type="button" onClick={() => onAsk(s.question)}
                    className="group rounded-xl border border-zinc-200 bg-white p-3.5 text-left transition hover:border-indigo-300 hover:shadow-sm
                               dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-indigo-500/50">
              <p className="line-clamp-2 text-sm font-medium group-hover:text-indigo-700 dark:group-hover:text-indigo-300">{s.question}</p>
              <p className="mt-1 flex items-center gap-1.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
                <Icon name="doc" className="size-3.5 shrink-0" /> <span className="truncate">{s.file}</span>
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
