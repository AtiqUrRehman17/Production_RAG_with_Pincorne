import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";

import { search } from "../../api/search";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Icon } from "../../components/Icon";
import { EmptyState } from "../../components/PageHeader";
import { SourceCard } from "../../components/SourceCard";
import { button, card, cx, fieldBase } from "../../components/ui";
import { plural } from "../../lib/format";

/** The passages that match a question, without writing an answer: shows what the chat can find. */
export function SearchPassages({ hasDocuments }: { hasDocuments: boolean }) {
  const mutation = useMutation({ mutationFn: (question: string) => search({ question, top_k: 10 }) });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = String(new FormData(event.currentTarget).get("q")).trim();
    if (question) mutation.mutate(question);
  }

  return (
    <div className="mt-6">
      <form onSubmit={submit} className="flex gap-2">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute inset-y-0 left-3 grid place-items-center text-zinc-400"><Icon name="search" className="size-4" /></span>
          <input name="q" required maxLength={4000} aria-label="Search your documents" disabled={!hasDocuments}
                 className={cx(fieldBase, "py-2.5 pl-9 pr-3")} placeholder="Find passages, e.g. “carry over vacation”" />
        </div>
        <button type="submit" disabled={mutation.isPending || !hasDocuments} className={button("primary")}>Search</button>
      </form>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        Shows the matching passages without writing an answer: useful to check what the chat can find.
      </p>
      <div className="mt-6 space-y-3">
        {mutation.isPending && [1, 2, 3].map((i) => (
          <div key={i} className={cx(card, "p-4")}>
            <div className="shimmer h-4 w-1/3 rounded" /><div className="shimmer mt-3 h-3 w-full rounded" /><div className="shimmer mt-2 h-3 w-4/5 rounded" />
          </div>
        ))}
        {mutation.isError && <ErrorMessage error={mutation.error} />}
        {mutation.isSuccess && (mutation.data.passages.length ? (
          <>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{plural(mutation.data.passages.length, "passage")} · ranked by {mutation.data.ranking}</p>
            <div className="grid gap-3 md:grid-cols-2">
              {mutation.data.passages.map((passage) => <SourceCard key={passage.number} source={passage} />)}
            </div>
          </>
        ) : <EmptyState title="Nothing found" text="No passage matches this. Try other words." />)}
        {mutation.isIdle && (
          <EmptyState title={hasDocuments ? "Search results appear here" : "Upload a document first"}
                      text={hasDocuments ? "Type a question or a few words above." : "There's nothing to search yet."} />
        )}
      </div>
    </div>
  );
}
