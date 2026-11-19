import { useState, type DragEvent } from "react";

import { MAX_FILE_SIZE_MB } from "../../api/documents";
import { Spinner } from "../../components/FullPageSpinner";
import { Icon } from "../../components/Icon";
import { FileChip } from "../../components/PageHeader";
import { badge, card, cx, iconButton, tone } from "../../components/ui";
import { fileType, formatBytes } from "../../lib/format";
import type { UploadItem } from "./useDocumentJobs";

export const ACCEPT = ".pdf,.docx,.txt";

export function DropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [over, setOver] = useState(false);
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    if (event.dataTransfer.files.length) onFiles([...event.dataTransfer.files]);
  };
  return (
    <div onDragEnter={(event) => { event.preventDefault(); setOver(true); }}
         onDragOver={(event) => event.preventDefault()}
         onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setOver(false); }}
         onDrop={onDrop}
         className={cx("rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors",
           over ? "border-blue-500 bg-blue-50/60 dark:bg-blue-500/10" : "border-slate-300 bg-slate-50/60 dark:border-slate-700 dark:bg-slate-900/40")}>
      <div className="mx-auto grid size-12 place-items-center rounded-xl bg-white text-blue-600 shadow-sm ring-1 ring-slate-200
                      dark:bg-slate-800 dark:text-blue-300 dark:ring-slate-700">
        <Icon name="upload" className="size-6" />
      </div>
      <p className="mt-4 text-sm font-medium">
        Drop files here, or{" "}
        <label className="cursor-pointer text-blue-600 hover:underline dark:text-blue-400">
          browse
          <input type="file" multiple accept={ACCEPT} className="sr-only"
                 onChange={(event) => { onFiles([...(event.target.files ?? [])]); event.target.value = ""; }} />
        </label>
      </p>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        PDF, DOCX or TXT · up to {MAX_FILE_SIZE_MB} MB each · scanned PDFs aren't supported yet
      </p>
    </div>
  );
}

const PHASES = {
  uploading: ["Uploading", tone.indigo],
  queued: ["Queued", tone.gray],
  processing: ["Processing", tone.indigo],
  done: ["Ready", tone.green],
  failed: ["Failed", tone.red],
} as const;

export function UploadList({ items, onDismiss }: { items: UploadItem[]; onDismiss: (key: string) => void }) {
  if (!items.length) return null;
  return (
    <div className="space-y-2" aria-live="polite">
      {items.map((item) => {
        const [word, color] = PHASES[item.phase];
        const finished = item.phase === "done" || item.phase === "failed";
        const step = {
          uploading: `Sending the file · ${item.progress}%`,
          queued: "Waiting for the background worker",
          processing: "Reading, splitting into passages and creating embeddings",
          done: item.message,
          failed: item.message,
        }[item.phase];
        return (
          <div key={item.key} className={cx(card, "fade-in flex items-center gap-3 p-3 sm:p-4")}>
            <FileChip type={fileType(item.name)} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="min-w-0 truncate text-sm font-medium" title={item.name}>{item.name}</p>
                <span className={cx(badge, color, "shrink-0")}>{item.phase === "done" && <Icon name="check" className="size-3" />}{word}</span>
              </div>
              {item.phase === "failed" ? (
                <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{step}</p>
              ) : (
                <>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                    <div className={cx("h-full rounded-full transition-all duration-300",
                                       item.phase === "done" ? "bg-emerald-500" : item.phase === "queued" ? "bg-slate-400 stripes" : "stripes bg-blue-500")}
                         style={{ width: `${item.phase === "uploading" ? Math.max(4, item.progress) : 100}%` }} />
                  </div>
                  <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                    {item.phase === "processing" && <Spinner className="size-3" />}
                    {step}{item.size != null && ` · ${formatBytes(item.size)}`}
                  </p>
                </>
              )}
            </div>
            {finished && (
              <button type="button" onClick={() => onDismiss(item.key)} className={iconButton} aria-label="Dismiss"><Icon name="x" className="size-4" /></button>
            )}
          </div>
        );
      })}
    </div>
  );
}
