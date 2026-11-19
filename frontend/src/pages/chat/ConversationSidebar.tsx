import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, NavLink } from "react-router";

import { listConversations } from "../../api/conversations";
import type { Conversation } from "../../api/types";
import { Icon } from "../../components/Icon";
import { button, cx, fieldBase, iconButton } from "../../components/ui";
import { plural } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";

function group(conversations: Conversation[]): [string, Conversation[]][] {
  const groups: [string, Conversation[]][] = [["Today", []], ["Previous 7 days", []], ["Older", []]];
  for (const c of conversations) {
    const hours = (Date.now() - new Date(c.updated_at).getTime()) / 3.6e6;
    groups[hours < 24 ? 0 : hours < 24 * 7 ? 1 : 2][1].push(c);
  }
  return groups.filter(([, items]) => items.length);
}

export function ConversationSidebar({
  mobile = false,
  onNewChat,
  onClose,
  documentCount,
  passageCount,
}: {
  mobile?: boolean;
  onNewChat: () => void;
  onClose?: () => void;
  documentCount: number;
  passageCount: number;
}) {
  const [search, setSearch] = useState("");
  const query = useInfiniteQuery({
    queryKey: queryKeys.conversations,
    queryFn: ({ pageParam }) => listConversations({ limit: 50, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const all = query.data?.pages.flatMap((page) => page.items) ?? [];
  const term = search.trim().toLowerCase();
  const groups = group(all.filter((c) => !term || (c.title || "New chat").toLowerCase().includes(term)));

  return (
    <aside
      className={cx(
        mobile ? "drawer-in flex h-full w-80 max-w-[85vw] shadow-2xl" : "hidden w-72 lg:flex",
        "shrink-0 flex-col border-r border-zinc-200/90 bg-zinc-50/70 backdrop-blur-md dark:border-zinc-800/90 dark:bg-zinc-950/70"
      )}
    >
      <div className="flex items-center gap-2 p-3 pb-2">
        <button
          type="button"
          onClick={onNewChat}
          className={cx(
            button("primary"),
            "flex-1 shadow-sm shadow-indigo-600/20 font-semibold tracking-wide"
          )}
        >
          <Icon name="plus" className="size-4" /> New chat
        </button>
        {mobile && (
          <button
            type="button"
            onClick={onClose}
            className={cx(iconButton, "size-9")}
            aria-label="Close menu"
          >
            <Icon name="x" />
          </button>
        )}
      </div>

      <div className="px-3 pb-2">
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 left-2.5 grid place-items-center text-zinc-400">
            <Icon name="search" className="size-3.5" />
          </span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search conversations…"
            aria-label="Search conversations"
            className={cx(fieldBase, "py-1.5 pl-8 pr-7 text-xs dark:bg-zinc-900/80")}
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute inset-y-0 right-2 grid place-items-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
            >
              <Icon name="x" className="size-3" />
            </button>
          )}
        </div>
      </div>

      <nav className="scroll-thin flex-1 space-y-0.5 overflow-y-auto px-2 pb-4" aria-label="Chats">
        {query.isPending &&
          Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="shimmer mx-1 mt-2.5 h-8 rounded-lg" />
          ))}

        {query.isError && (
          <p className="px-3 py-6 text-center text-xs text-rose-600 dark:text-rose-400">
            {query.error.message}
          </p>
        )}

        {query.isSuccess && !all.length && (
          <div className="px-3 py-8 text-center">
            <Icon name="chat" className="mx-auto size-6 text-zinc-300 dark:text-zinc-600" />
            <p className="mt-2 text-xs font-medium text-zinc-600 dark:text-zinc-400">
              No conversations yet
            </p>
            <p className="mt-0.5 text-[11px] text-zinc-400 dark:text-zinc-500">
              Your inquiry history will appear here.
            </p>
          </div>
        )}

        {query.isSuccess && all.length > 0 && !groups.length && (
          <p className="px-3 py-6 text-center text-xs text-zinc-500 dark:text-zinc-400">
            No chats match "{search}".
          </p>
        )}

        {groups.map(([label, items]) => (
          <div key={label} className="mt-2">
            <p className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              {label}
            </p>
            {items.map((c) => (
              <NavLink
                key={c.id}
                to={`/chat/${c.id}`}
                onClick={onClose}
                className={({ isActive }) =>
                  cx(
                    "group relative flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors",
                    isActive
                      ? "bg-white font-semibold text-zinc-900 shadow-xs ring-1 ring-zinc-200 dark:bg-zinc-800/90 dark:text-white dark:ring-zinc-700"
                      : "text-zinc-600 hover:bg-zinc-200/60 dark:text-zinc-400 dark:hover:bg-zinc-800/50"
                  )
                }
              >
                <Icon
                  name="chat"
                  className="size-3.5 shrink-0 text-zinc-400 group-hover:text-indigo-500"
                />
                <span className="min-w-0 flex-1 truncate">{c.title || "New chat"}</span>
                {c.document_ids && (
                  <span
                    className="shrink-0 rounded-xs bg-zinc-200/80 px-1 py-0.5 text-[9px] font-mono text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300"
                    title={`Restricted to ${c.document_ids.length} document${c.document_ids.length > 1 ? "s" : ""}`}
                  >
                    {c.document_ids.length} doc{c.document_ids.length > 1 ? "s" : ""}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        ))}

        {query.hasNextPage && (
          <button
            type="button"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            className={cx(button("ghost", "sm"), "mt-2 w-full text-xs")}
          >
            {query.isFetchingNextPage ? "Loading…" : "Load older chats"}
          </button>
        )}
      </nav>

      {/* Footer knowledge summary */}
      <div className="border-t border-zinc-200/80 p-3 text-xs text-zinc-500 dark:border-zinc-800/80 dark:text-zinc-400">
        <Link
          to="/documents"
          className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-zinc-200/60 dark:hover:bg-zinc-800"
        >
          <span className="flex items-center gap-2 font-medium">
            <Icon name="doc" className="size-4 text-indigo-500" />
            <span>Knowledge Base</span>
          </span>
          <span className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500">
            {plural(documentCount, "doc")} · {plural(passageCount, "passage")}
          </span>
        </Link>
      </div>
    </aside>
  );
}
