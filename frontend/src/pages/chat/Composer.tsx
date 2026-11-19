import { useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Icon } from "../../components/Icon";

export function Composer({
  streaming,
  disabled,
  scopeLabel,
  onSend,
  onStop,
  onOpenScope,
}: {
  streaming: boolean;
  disabled: boolean;
  scopeLabel?: string;
  onSend: (question: string) => void;
  onStop: () => void;
  onOpenScope?: () => void;
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
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      send(event);
    }
  }

  return (
    <div className="shrink-0 px-3 pb-3 pt-2 sm:px-6 sm:pb-5">
      <form onSubmit={send} className="mx-auto max-w-3xl">
        <div className="relative rounded-2xl border border-slate-200/90 bg-white p-2 shadow-lg shadow-slate-200/50 transition-all duration-200 focus-within:border-blue-500/80 focus-within:ring-4 focus-within:ring-blue-500/15 dark:border-slate-800 dark:bg-slate-900 dark:shadow-none dark:focus-within:border-blue-400">
          <label htmlFor="composer" className="sr-only">
            Your question
          </label>
          <textarea
            id="composer"
            ref={box}
            rows={1}
            maxLength={4000}
            value={draft}
            autoFocus
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question about your documents…"
            className="scroll-thin max-h-48 w-full resize-none bg-transparent px-3 py-2 text-[15px] leading-relaxed text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
          />

          <div className="flex items-center justify-between border-t border-slate-100 px-2 pt-2 dark:border-slate-800/80">
            {/* Scope pill indicator */}
            {scopeLabel && (
              <button
                type="button"
                onClick={onOpenScope}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200/70 bg-slate-50/80 px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-800 dark:bg-slate-800/60 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                title="Change searched documents"
              >
                <Icon name="layers" className="size-3.5 text-blue-500" />
                <span className="max-w-[140px] truncate sm:max-w-xs">{scopeLabel}</span>
              </button>
            )}

            {!scopeLabel && <div />}

            <div className="flex items-center gap-2">
              {draft.length > 3000 && (
                <span className="text-[11px] font-mono text-slate-400">
                  {draft.length}/4000
                </span>
              )}

              {streaming ? (
                <button
                  type="button"
                  onClick={onStop}
                  title="Stop generating"
                  className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-slate-900 px-3 text-xs font-semibold text-white shadow-xs transition hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
                >
                  <span className="size-2 rounded-xs bg-rose-500 animate-pulse" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  title="Send message"
                  disabled={!draft.trim() || disabled}
                  className="grid size-9 place-items-center rounded-xl bg-blue-600 text-white shadow-sm shadow-blue-600/30 transition hover:bg-blue-500 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400 disabled:shadow-none dark:disabled:bg-slate-800 dark:disabled:text-slate-600"
                >
                  <Icon name="send" className="size-4" />
                </button>
              )}
            </div>
          </div>
        </div>

        <p className="mt-2 hidden text-center text-[11px] text-slate-400 sm:block dark:text-slate-500">
          <kbd className="rounded border border-slate-200 bg-slate-100 px-1 py-0.5 text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">Enter</kbd> to send · <kbd className="rounded border border-slate-200 bg-slate-100 px-1 py-0.5 text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">Shift + Enter</kbd> for new line · Responses grounded in verifiable document passages
        </p>
      </form>
    </div>
  );
}
