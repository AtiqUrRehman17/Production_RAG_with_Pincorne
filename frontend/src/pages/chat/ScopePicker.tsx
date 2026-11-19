import { useEffect, useRef, useState } from "react";

import type { DocumentInfo } from "../../api/types";
import { Icon } from "../../components/Icon";
import { button, cx, fieldBase } from "../../components/ui";
import { fileType } from "../../lib/format";
import { toast } from "../../lib/toast";

/** Which documents a chat searches: null = all of them. */
export function ScopePicker({
  documents,
  selected,
  onChange,
}: {
  documents: DocumentInfo[];
  selected: string[] | null;
  onChange: (documentIds: string[] | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const box = useRef<HTMLDivElement>(null);

  const existing = selected?.filter((id) => documents.some((d) => d.document_id === id)) ?? null;

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle(id: string) {
    const current = existing ?? documents.map((d) => d.document_id);
    const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    if (!next.length) {
      toast("Pick at least one document to search.", "error");
      return;
    }
    onChange(next.length === documents.length ? null : next);
  }

  const filteredDocs = documents.filter((d) =>
    !search.trim() || d.file_name.toLowerCase().includes(search.trim().toLowerCase())
  );

  const label = existing
    ? `${existing.length} of ${documents.length} docs`
    : `All documents (${documents.length})`;

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        title="Filter which documents this chat searches"
        className={cx(
          button("secondary", "sm"),
          "gap-1.5 shadow-2xs font-medium text-xs",
          existing && "border-blue-300 bg-blue-50/50 text-blue-700 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300"
        )}
        disabled={!documents.length}
      >
        <Icon name="layers" className="size-3.5 text-blue-500" />
        <span className="hidden sm:inline">{label}</span>
        <span className="sm:hidden">{existing ? existing.length : "All"}</span>
        <Icon name="down" className={cx("size-3 transition-transform duration-200", open && "rotate-180")} />
      </button>

      {open && (
        <div className="fade-in absolute right-0 top-full z-40 mt-2 w-84 max-w-[calc(100vw-1.5rem)] rounded-xl border border-slate-200/90 bg-white p-2.5 shadow-xl backdrop-blur-md dark:border-slate-700 dark:bg-slate-900">
          <div className="px-1 pb-2">
            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
              Retrieval Scope Filter
            </p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Restrict Pinecone vector queries to specific documents.
            </p>
          </div>

          {documents.length > 5 && (
            <div className="mb-2 px-1">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter files…"
                className={cx(fieldBase, "py-1 px-2.5 text-xs")}
              />
            </div>
          )}

          <div className="flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-1.5 dark:bg-slate-800/60">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={!existing}
                onChange={() => onChange(null)}
                className="size-3.5 rounded accent-blue-600"
              />
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                All Documents
              </span>
            </label>
            <span className="text-[10px] text-slate-400 font-mono">
              {documents.length} available
            </span>
          </div>

          <div className="my-1.5 border-t border-slate-100 dark:border-slate-800" />

          <div className="scroll-thin max-h-60 space-y-0.5 overflow-y-auto px-0.5">
            {filteredDocs.map((d) => {
              const isChecked = !existing || existing.includes(d.document_id);
              const ext = fileType(d.file_name);
              return (
                <label
                  key={d.document_id}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 transition hover:bg-slate-100/70 dark:hover:bg-slate-800/60"
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggle(d.document_id)}
                    className="size-3.5 rounded accent-blue-600"
                  />
                  <span className="min-w-0 flex-1 truncate text-xs text-slate-700 dark:text-slate-300" title={d.file_name}>
                    {d.file_name}
                  </span>
                  <span className="rounded-xs bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-400 dark:bg-slate-800 dark:text-slate-500">
                    {ext}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
