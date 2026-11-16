import { useEffect, useRef, useState } from "react";

import type { DocumentInfo } from "../../api/types";
import { Icon } from "../../components/Icon";
import { button, cx } from "../../components/ui";
import { fileType } from "../../lib/format";
import { toast } from "../../lib/toast";

/** Which documents a chat searches: null = all of them. */
export function ScopePicker({ documents, selected, onChange }: {
  documents: DocumentInfo[];
  selected: string[] | null;
  onChange: (documentIds: string[] | null) => void;
}) {
  const [open, setOpen] = useState(false);
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
      toast("Pick at least one document.", "error");
      return;
    }
    onChange(next.length === documents.length ? null : next);
  }

  const label = existing ? `${existing.length} of ${documents.length} documents` : "All documents";
  return (
    <div ref={box} className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} title="Which documents this chat searches"
              className={cx(button("secondary", "sm"), "gap-1.5")} disabled={!documents.length}>
        <Icon name="layers" className="size-4" />
        <span className="hidden sm:inline">{label}</span>
        <span className="sm:hidden">{existing ? existing.length : "All"}</span>
        <Icon name="down" className="size-3.5" />
      </button>
      {open && (
        <div className="fade-in absolute right-0 top-full z-30 mt-2 w-80 max-w-[calc(100vw-1.5rem)] rounded-xl border border-zinc-200 bg-white p-2
                        shadow-xl dark:border-zinc-700 dark:bg-zinc-900">
          <p className="px-2 pb-2 pt-1 text-xs text-zinc-500 dark:text-zinc-400">This chat only searches the documents you pick.</p>
          <label className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800">
            <input type="checkbox" checked={!existing} onChange={() => onChange(null)} className="size-4 rounded accent-indigo-600" />
            <span className="text-sm font-medium">All documents</span>
          </label>
          <div className="my-1 border-t border-zinc-100 dark:border-zinc-800" />
          <div className="scroll-thin max-h-72 overflow-y-auto">
            {documents.map((d) => (
              <label key={d.document_id} className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800">
                <input type="checkbox" checked={!existing || existing.includes(d.document_id)} onChange={() => toggle(d.document_id)}
                       className="size-4 rounded accent-indigo-600" />
                <span className="min-w-0 flex-1 truncate text-sm" title={d.file_name}>{d.file_name}</span>
                <span className="text-[10px] font-semibold uppercase text-zinc-400">{fileType(d.file_name)}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
