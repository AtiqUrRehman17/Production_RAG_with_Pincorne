import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ErrorMessage } from "./ErrorMessage";
import { Icon } from "./Icon";
import { button, cx } from "./ui";

function useEscape(onClose: () => void): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
}

/** A centred dialog (a sheet from the bottom on phones). */
export function Modal({ onClose, wide = false, label, children }: {
  onClose: () => void;
  wide?: boolean;
  label: string;
  children: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEscape(onClose);
  useEffect(() => {
    panel.current?.querySelector<HTMLElement>("input, textarea, select")?.focus();
  }, []);
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={label}>
      <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-[2px]" onClick={onClose} />
      <div ref={panel}
           className={cx("fade-in pb-safe relative max-h-[90dvh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl",
                         "sm:rounded-2xl sm:p-6 dark:bg-slate-900 dark:ring-1 dark:ring-slate-800", wide ? "sm:max-w-lg" : "sm:max-w-md")}>
        {children}
      </div>
    </div>,
    document.body,
  );
}

/** A panel sliding in from the right (full screen on phones). */
export function Drawer({ onClose, label, header, children }: {
  onClose: () => void;
  label: string;
  header: ReactNode;
  children: ReactNode;
}) {
  useEscape(onClose);
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={label}>
      <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]" onClick={onClose} />
      <aside className="slide-in scroll-thin relative h-full w-full overflow-y-auto bg-white shadow-2xl sm:max-w-2xl
                        dark:bg-slate-950 dark:ring-1 dark:ring-slate-800">
        <div className="sticky top-0 z-10 flex items-start gap-3 border-b border-slate-200 bg-white/95 p-4 backdrop-blur
                        sm:p-5 dark:border-slate-800 dark:bg-slate-950/95">
          <div className="min-w-0 flex-1">{header}</div>
          <button type="button" onClick={onClose} className="inline-grid size-9 place-items-center rounded-lg text-slate-500
                  hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close"><Icon name="x" /></button>
        </div>
        <div className="space-y-5 p-4 sm:p-5">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}

/** "Are you sure?" for deleting things. `onConfirm` may throw; its error is shown in the dialog. */
export function ConfirmDialog({ title, text, confirmLabel, onConfirm, onClose, children }: {
  title: string;
  text: string;
  confirmLabel: string;
  onConfirm: (form: HTMLFormElement) => Promise<void> | void;
  onClose: () => void;
  children?: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onConfirm(event.currentTarget);
      onClose();
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <Modal onClose={busy ? () => {} : onClose} label={title}>
      <div className="flex gap-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-full bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400">
          <Icon name="trash" />
        </div>
        <div className="min-w-0">
          <h2 className="font-semibold wrap-break-word">{title}</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{text}</p>
        </div>
      </div>
      <form onSubmit={submit}>
        {children}
        {error != null && <div className="mt-4"><ErrorMessage error={error} /></div>}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={busy} className={button("secondary")}>Cancel</button>
          <button type="submit" disabled={busy} className={button("danger")}>{busy ? "Please wait…" : confirmLabel}</button>
        </div>
      </form>
    </Modal>
  );
}
