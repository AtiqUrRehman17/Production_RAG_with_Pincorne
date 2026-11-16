import { useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Icon } from "../../components/Icon";

export function Composer({ streaming, disabled, onSend, onStop }: {
  streaming: boolean;
  disabled: boolean; // e.g. while a new chat is being created
  onSend: (question: string) => void;
  onStop: () => void;
}) {
  const [draft, setDraft] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
  }, [draft]);

  function send(event?: FormEvent) {
    event?.preventDefault();
    const question = draft.trim();
    if (!question || streaming || disabled) return;
    onSend(question);
    setDraft("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) send(event);
  }

  return (
    <div className="shrink-0 px-3 pb-3 pt-2 sm:px-6 sm:pb-5">
      <form onSubmit={send} className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-zinc-300 bg-white p-2 pl-4 shadow-sm transition
                        focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-500/15 dark:border-zinc-700 dark:bg-zinc-900">
          <label htmlFor="composer" className="sr-only">Your question</label>
          <textarea id="composer" ref={box} rows={1} maxLength={4000} value={draft} autoFocus
                    onChange={(event) => setDraft(event.target.value)} onKeyDown={onKeyDown}
                    placeholder="Ask a question about your documents…"
                    className="scroll-thin max-h-48 flex-1 resize-none bg-transparent py-2 text-[15px] outline-none placeholder:text-zinc-400" />
          {streaming ? (
            <button type="button" onClick={onStop} title="Stop"
                    className="grid size-10 shrink-0 place-items-center rounded-xl bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-white dark:text-zinc-900">
              <Icon name="stop" className="size-4" />
            </button>
          ) : (
            <button type="submit" title="Send" disabled={!draft.trim() || disabled}
                    className="grid size-10 shrink-0 place-items-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-500
                               disabled:bg-zinc-200 disabled:text-zinc-400 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-500">
              <Icon name="send" />
            </button>
          )}
        </div>
        <p className="mt-2 hidden text-center text-[11px] text-zinc-400 sm:block">
          Enter to send · Shift + Enter for a new line · Answers can be wrong, so check the sources
        </p>
      </form>
    </div>
  );
}
