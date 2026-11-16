import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { removeFeedback, setFeedback } from "../../api/feedback";
import type { ConversationDetail, Feedback, Message, Rating } from "../../api/types";
import { Icon } from "../../components/Icon";
import { Logo } from "../../components/Logo";
import { SourceCard } from "../../components/SourceCard";
import { button, cx, field, iconButton } from "../../components/ui";
import { AnswerText } from "../../lib/answerText";
import { formatRelative } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import { toast } from "../../lib/toast";
import type { PendingAnswer } from "./useChatStream";

export function UserMessage({ content }: { content: string }) {
  return (
    <div className="fade-in flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap wrap-break-word rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-[15px]
                      leading-relaxed text-white sm:max-w-[75%]">
        {content}
      </div>
    </div>
  );
}

const STREAMING_CITATIONS = Array.from({ length: 30 }, (_, i) => i + 1);

/** The answer while it is being written. */
export function PendingMessage({ pending }: { pending: PendingAnswer }) {
  return (
    <div className="fade-in flex gap-3">
      <Logo size="sm" />
      <div className="min-w-0 flex-1 pt-0.5">
        {pending.text ? (
          <div className="caret space-y-3 text-[15px] leading-7 text-zinc-700 dark:text-zinc-300">
            <AnswerText text={pending.text} citations={STREAMING_CITATIONS} onCite={() => {}} />
          </div>
        ) : (
          <div className="flex items-center gap-2.5 py-1.5 text-sm text-zinc-500 dark:text-zinc-400" role="status">
            <span className="dots flex gap-1 text-indigo-500"><span /><span /><span /></span>Searching your documents…
          </div>
        )}
      </div>
    </div>
  );
}

const FEEDBACK_TAGS = ["Wrong answer", "Missing information", "Wrong source", "Too long"];

export function AssistantMessage({ message, conversationId, isAdmin, onRetry }: {
  message: Message;
  conversationId: string;
  isAdmin: boolean;
  onRetry?: () => void;
}) {
  const queryClient = useQueryClient();
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [commentOpen, setCommentOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const citations = message.citations ?? [];

  useEffect(() => {
    if (highlighted == null) return;
    document.getElementById(`src-${message.id}-${highlighted}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const timer = setTimeout(() => setHighlighted(null), 2200);
    return () => clearTimeout(timer);
  }, [highlighted, message.id]);

  function showSource(n: number) {
    setSourcesOpen(true);
    setHighlighted(n);
  }

  function saveFeedback(feedback: Feedback | null) {
    queryClient.setQueryData<ConversationDetail>(queryKeys.conversation(conversationId), (old) => old && {
      ...old, messages: old.messages.map((m) => (m.id === message.id ? { ...m, feedback } : m)),
    });
  }

  async function rate(rating: Rating) {
    setBusy(true);
    try {
      if (message.feedback?.rating === rating) {
        await removeFeedback(message.id);
        saveFeedback(null);
        setCommentOpen(false);
      } else {
        saveFeedback(await setFeedback(message.id, { rating }));
        setCommentOpen(rating === "down");
        if (rating === "up") toast("Thanks for the feedback!");
      }
    } catch (error) {
      toast(error instanceof Error ? error.message : "The feedback could not be saved.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function sendComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const comment = String(new FormData(event.currentTarget).get("comment")).trim();
    setCommentOpen(false);
    if (!comment) return;
    try {
      saveFeedback(await setFeedback(message.id, { rating: "down", comment }));
      toast("Thanks, your feedback helps improve the answers.");
    } catch (error) {
      toast(error instanceof Error ? error.message : "The feedback could not be saved.", "error");
    }
  }

  function copy() {
    navigator.clipboard.writeText(message.content).then(() => toast("Answer copied.", "info"),
                                                       () => toast("Copying is not allowed in this browser.", "error"));
  }

  let body;
  if (message.status === "error") {
    body = (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-sm text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
        <div className="flex gap-2.5">
          <Icon name="alert" className="size-5 shrink-0 text-rose-500" />
          <div className="min-w-0">
            <p className="font-medium">The answer could not be created</p>
            <p className="mt-0.5 text-rose-800/90 dark:text-rose-200/80">{message.error ?? "Something went wrong while answering."}</p>
            {message.request_id && <p className="mt-2 font-mono text-[11px] text-rose-700/70 dark:text-rose-300/60">Request ID: {message.request_id}</p>}
          </div>
        </div>
        {onRetry && (
          <button type="button" onClick={onRetry} className={cx(button("secondary", "sm"), "mt-3")}>
            <Icon name="refresh" className="size-3.5" /> Try again
          </button>
        )}
      </div>
    );
  } else if (message.found === false) {
    body = (
      <div className="flex gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
        <Icon name="info" className="size-5 shrink-0 text-amber-500" />
        <div>
          <p className="font-medium">I couldn't find this in your documents.</p>
          <p className="mt-0.5 text-amber-800/90 dark:text-amber-100/70">Try different words, or check which documents this chat searches.</p>
        </div>
      </div>
    );
  } else {
    body = (
      <div className="space-y-3 wrap-break-word text-[15px] leading-7 text-zinc-700 dark:text-zinc-300">
        <AnswerText text={message.content} citations={citations.map((c) => c.number)} onCite={showSource} />
      </div>
    );
  }

  const files = [...new Set(citations.map((c) => c.file_name ?? c.label))];
  const rating = message.feedback?.rating;

  return (
    <div className="fade-in flex gap-3">
      <Logo size="sm" />
      <div className="min-w-0 flex-1 pt-0.5">
        {message.searched_for && (
          <p className="mb-2 flex items-start gap-1.5 text-xs text-zinc-400" title="Your follow-up was rewritten so it can be searched on its own">
            <Icon name="search" className="mt-px size-3.5 shrink-0" /> Searched for “{message.searched_for}”
          </p>
        )}
        {body}

        {citations.length > 0 && (
          <div className="mt-3">
            <button type="button" onClick={() => setSourcesOpen(!sourcesOpen)} aria-expanded={sourcesOpen}
                    className="inline-flex max-w-full items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-xs
                               font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800">
              <Icon name="doc" className="size-3.5 shrink-0" />
              <span className="truncate">{citations.length} source{citations.length > 1 ? "s" : ""} · {files.length === 1 ? files[0] : `${files.length} files`}</span>
              <Icon name="down" className={cx("size-3.5 shrink-0 transition-transform", sourcesOpen && "rotate-180")} />
            </button>
            {sourcesOpen && (
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {citations.map((source) => (
                  <SourceCard key={source.number} source={source} id={`src-${message.id}-${source.number}`}
                              highlighted={highlighted === source.number} />
                ))}
              </div>
            )}
          </div>
        )}

        {message.status !== "error" && (
          <div className="mt-2 flex flex-wrap items-center gap-0.5">
            {message.found !== false && (
              <button type="button" onClick={copy} className={iconButton} title="Copy answer"><Icon name="copy" className="size-4" /></button>
            )}
            <button type="button" onClick={() => rate("up")} disabled={busy} title="Good answer" aria-pressed={rating === "up"}
                    className={cx(iconButton, rating === "up" && "text-emerald-600! dark:text-emerald-400!")}>
              <Icon name="thumb" className="size-4" />
            </button>
            <button type="button" onClick={() => rate("down")} disabled={busy} title="Bad answer" aria-pressed={rating === "down"}
                    className={cx(iconButton, rating === "down" && "text-rose-600! dark:text-rose-400!")}>
              <Icon name="thumb" className="size-4 rotate-180" />
            </button>
            <span className="ml-2 flex items-center gap-1 text-xs text-zinc-400">
              <Icon name="clock" className="size-3.5" />
              {message.latency_ms != null && `${(message.latency_ms / 1000).toFixed(1)} s · `}{formatRelative(message.created_at)}
            </span>
            {isAdmin && message.trace_id && (
              <Link to={`/admin?tab=traces&trace=${message.trace_id}`} className="ml-2 inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-indigo-600 dark:hover:text-indigo-400">
                <Icon name="list" className="size-3.5" /> Trace
              </Link>
            )}
          </div>
        )}

        {commentOpen && (
          <form onSubmit={sendComment} className="fade-in mt-2 rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
            <label className="text-xs font-medium" htmlFor={`fb-${message.id}`}>What was wrong? <span className="font-normal text-zinc-400">(optional)</span></label>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {FEEDBACK_TAGS.map((tag) => (
                <button key={tag} type="button"
                        onClick={(event) => {
                          const box = event.currentTarget.form?.elements.namedItem("comment") as HTMLTextAreaElement;
                          box.value = box.value ? `${box.value}, ${tag}` : tag;
                          box.focus();
                        }}
                        className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs hover:border-indigo-300 dark:border-zinc-700 dark:bg-zinc-800">
                  {tag}
                </button>
              ))}
            </div>
            <textarea id={`fb-${message.id}`} name="comment" rows={2} maxLength={2000} className={cx(field, "mt-2 resize-none")} placeholder="Tell us more…" />
            <div className="mt-2 flex justify-end gap-2">
              <button type="button" onClick={() => setCommentOpen(false)} className={button("ghost", "sm")}>Skip</button>
              <button type="submit" className={button("primary", "sm")}>Send feedback</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
