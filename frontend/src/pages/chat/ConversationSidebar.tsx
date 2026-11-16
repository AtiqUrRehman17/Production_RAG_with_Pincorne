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

export function ConversationSidebar({ mobile = false, onNewChat, onClose, documentCount, passageCount }: {
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
    <aside className={cx(mobile ? "drawer-in flex h-full w-80 max-w-[85vw] shadow-2xl" : "hidden w-72 lg:flex",
                         "shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900")}>
      <div className="flex items-center gap-2 p-3">
        <button type="button" onClick={onNewChat} className={cx(button("primary"), "flex-1")}><Icon name="plus" className="size-4" /> New chat</button>
        {mobile && <button type="button" onClick={onClose} className={cx(iconButton, "size-9")} aria-label="Close"><Icon name="x" /></button>}
      </div>
      <div className="px-3">
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 left-2.5 grid place-items-center text-zinc-400"><Icon name="search" className="size-4" /></span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search chats" aria-label="Search chats"
                 className={cx(fieldBase, "py-1.5 pl-8 pr-3 dark:bg-zinc-950")} />
        </div>
      </div>
      <nav className="scroll-thin flex-1 space-y-0.5 overflow-y-auto px-2 pb-4" aria-label="Chats">
        {query.isPending && Array.from({ length: 5 }, (_, i) => <div key={i} className="shimmer mx-1 mt-3 h-8 rounded-lg" />)}
        {query.isError && <p className="px-3 py-6 text-center text-sm text-rose-600 dark:text-rose-400">{query.error.message}</p>}
        {query.isSuccess && !all.length && (
          <p className="px-3 py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">No chats yet. Ask your first question.</p>
        )}
        {query.isSuccess && all.length > 0 && !groups.length && (
          <p className="px-3 py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">No chats match “{search}”.</p>
        )}
        {groups.map(([label, items]) => (
          <div key={label}>
            <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{label}</p>
            {items.map((c) => (
              <NavLink key={c.id} to={`/chat/${c.id}`} onClick={onClose}
                       className={({ isActive }) => cx("flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                         isActive ? "bg-white font-medium text-zinc-900 shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-white dark:ring-zinc-700"
                                  : "text-zinc-600 hover:bg-zinc-200/60 dark:text-zinc-400 dark:hover:bg-zinc-800/60")}>
                <span className="min-w-0 flex-1 truncate">{c.title || "New chat"}</span>
                {c.document_ids && (
                  <span className="shrink-0 text-zinc-400" title={`Uses ${c.document_ids.length} selected document${c.document_ids.length > 1 ? "s" : ""}`}>
                    <Icon name="layers" className="size-3.5" />
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
        {query.hasNextPage && (
          <button type="button" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage}
                  className={cx(button("ghost", "sm"), "mt-2 w-full")}>
            {query.isFetchingNextPage ? "Loading…" : "Show older chats"}
          </button>
        )}
      </nav>
      <div className="border-t border-zinc-200 p-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        <Link to="/documents" className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-zinc-200/60 dark:hover:bg-zinc-800">
          <Icon name="doc" className="size-4" /> {plural(documentCount, "document")} · {plural(passageCount, "passage")}
        </Link>
      </div>
    </aside>
  );
}
