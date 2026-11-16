import type { ReactNode } from "react";

import type { DocumentInfo } from "../../api/types";
import { Spinner } from "../../components/FullPageSpinner";
import { Icon } from "../../components/Icon";
import { FileChip } from "../../components/PageHeader";
import { button, card, cx, iconButton } from "../../components/ui";
import { fileType, formatBytes, formatDate, formatRelative, plural } from "../../lib/format";

export function DocumentList({ documents, deleting, onChat, onDelete }: {
  documents: DocumentInfo[];
  deleting: Record<string, string>;
  onChat: (document: DocumentInfo) => void;
  onDelete: (document: DocumentInfo) => void;
}) {
  const actions = (d: DocumentInfo): ReactNode => (d.document_id in deleting ? (
    <span className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400"><Spinner className="size-3" />Deleting…</span>
  ) : (
    <>
      <button type="button" onClick={() => onChat(d)} className={button("ghost", "sm")} title="Start a chat with only this document">
        <Icon name="chat" className="size-4" /><span className="hidden lg:inline">Chat</span>
      </button>
      <button type="button" onClick={() => onDelete(d)} className={cx(iconButton, "hover:text-rose-600!")} title="Delete">
        <Icon name="trash" className="size-4" />
      </button>
    </>
  ));

  return (
    <>
      <div className={cx(card, "hidden overflow-hidden sm:block")}>
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <tr>
              <th className="px-4 py-2.5 font-medium">Name</th>
              <th className="px-4 py-2.5 font-medium">Pages</th>
              <th className="px-4 py-2.5 font-medium">Passages</th>
              <th className="px-4 py-2.5 font-medium">Size</th>
              <th className="px-4 py-2.5 font-medium">Added</th>
              <th className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {documents.map((d) => (
              <tr key={d.document_id} className={d.document_id in deleting ? "opacity-50" : "hover:bg-zinc-50/70 dark:hover:bg-zinc-800/30"}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <FileChip type={fileType(d.file_name)} />
                    <span className="max-w-[16rem] truncate font-medium lg:max-w-sm" title={d.file_name}>{d.file_name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 tabular-nums text-zinc-500 dark:text-zinc-400">{d.page_count ?? "–"}</td>
                <td className="px-4 py-3 tabular-nums text-zinc-500 dark:text-zinc-400">{d.chunk_count}</td>
                <td className="px-4 py-3 tabular-nums text-zinc-500 dark:text-zinc-400">{formatBytes(d.size_bytes)}</td>
                <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400" title={formatDate(d.created_at)}>{formatRelative(d.created_at)}</td>
                <td className="px-4 py-3"><div className="flex items-center justify-end gap-1">{actions(d)}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-2 sm:hidden">
        {documents.map((d) => (
          <div key={d.document_id} className={cx(card, "flex items-center gap-3 p-3", d.document_id in deleting && "opacity-50")}>
            <FileChip type={fileType(d.file_name)} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{d.file_name}</p>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                {d.page_count ? `${plural(d.page_count, "page")} · ` : ""}{plural(d.chunk_count, "passage")} · {formatBytes(d.size_bytes)} · {formatRelative(d.created_at)}
              </p>
            </div>
            <div className="flex items-center">{actions(d)}</div>
          </div>
        ))}
      </div>
    </>
  );
}
