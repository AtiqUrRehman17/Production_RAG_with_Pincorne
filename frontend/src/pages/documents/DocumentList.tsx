import { useState, type ReactNode } from "react";

import type { DocumentInfo } from "../../api/types";
import { Spinner } from "../../components/FullPageSpinner";
import { Icon } from "../../components/Icon";
import { FileChip } from "../../components/PageHeader";
import { button, card, cx, fieldBase, iconButton } from "../../components/ui";
import { fileType, formatBytes, formatDate, formatRelative, plural } from "../../lib/format";

export function DocumentList({
  documents,
  deleting,
  onChat,
  onDelete,
}: {
  documents: DocumentInfo[];
  deleting: Record<string, string>;
  onChat: (document: DocumentInfo) => void;
  onDelete: (document: DocumentInfo) => void;
}) {
  const [filter, setFilter] = useState("");

  const filtered = documents.filter((d) =>
    !filter.trim() || d.file_name.toLowerCase().includes(filter.trim().toLowerCase())
  );

  const actions = (d: DocumentInfo): ReactNode =>
    d.document_id in deleting ? (
      <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">
        <Spinner className="size-3" /> Deleting…
      </span>
    ) : (
      <>
        <button
          type="button"
          onClick={() => onChat(d)}
          className={cx(button("ghost", "sm"), "gap-1 text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400")}
          title="Start a new chat dedicated to this document"
        >
          <Icon name="chat" className="size-3.5" />
          <span>Chat</span>
        </button>
        <button
          type="button"
          onClick={() => onDelete(d)}
          className={cx(iconButton, "size-8 hover:text-rose-600!")}
          title="Delete document and vectors"
        >
          <Icon name="trash" className="size-3.5" />
        </button>
      </>
    );

  return (
    <div className="space-y-3">
      {documents.length > 4 && (
        <div className="relative max-w-sm">
          <span className="pointer-events-none absolute inset-y-0 left-2.5 grid place-items-center text-zinc-400">
            <Icon name="search" className="size-3.5" />
          </span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search documents by name…"
            className={cx(fieldBase, "py-1.5 pl-8 pr-3 text-xs")}
          />
        </div>
      )}

      {/* Desktop table */}
      <div className={cx(card, "hidden overflow-hidden sm:block shadow-xs")}>
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200/90 bg-zinc-50/80 text-left text-xs font-semibold text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/80 dark:text-zinc-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Document Name</th>
              <th className="px-4 py-3 font-semibold">Pages</th>
              <th className="px-4 py-3 font-semibold">Chunks</th>
              <th className="px-4 py-3 font-semibold">File Size</th>
              <th className="px-4 py-3 font-semibold">Uploaded</th>
              <th className="px-4 py-3 text-right"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/80">
            {filtered.map((d) => (
              <tr
                key={d.document_id}
                className={cx(
                  "transition-colors",
                  d.document_id in deleting ? "opacity-50" : "hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40"
                )}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <FileChip type={fileType(d.file_name)} />
                    <div className="min-w-0">
                      <p className="max-w-[18rem] truncate font-medium text-zinc-900 lg:max-w-md dark:text-zinc-100" title={d.file_name}>
                        {d.file_name}
                      </p>
                      <p className="font-mono text-[10px] text-zinc-400 dark:text-zinc-500">
                        {d.document_id.slice(0, 8)}…
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 tabular-nums text-zinc-600 dark:text-zinc-400">
                  {d.page_count ?? "–"}
                </td>
                <td className="px-4 py-3 tabular-nums font-medium text-indigo-600 dark:text-indigo-400">
                  {d.chunk_count}
                </td>
                <td className="px-4 py-3 tabular-nums text-zinc-600 dark:text-zinc-400">
                  {formatBytes(d.size_bytes)}
                </td>
                <td className="px-4 py-3 text-xs text-zinc-500 dark:text-zinc-400" title={formatDate(d.created_at)}>
                  {formatRelative(d.created_at)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1.5">{actions(d)}</div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-xs text-zinc-500">
                  No documents match "{filter}".
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile view */}
      <div className="space-y-2 sm:hidden">
        {filtered.map((d) => (
          <div
            key={d.document_id}
            className={cx(card, "flex items-center gap-3 p-3.5", d.document_id in deleting && "opacity-50")}
          >
            <FileChip type={fileType(d.file_name)} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">{d.file_name}</p>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                {d.page_count ? `${plural(d.page_count, "page")} · ` : ""}
                {plural(d.chunk_count, "passage")} · {formatBytes(d.size_bytes)}
              </p>
            </div>
            <div className="flex items-center">{actions(d)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
