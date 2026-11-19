import type { ReactNode } from "react";

import { cx } from "./ui";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
      </div>
      {actions}
    </div>
  );
}

export function Tabs<T extends string>({ items, active, onChange }: {
  items: { key: T; label: string; count?: ReactNode }[];
  active: T;
  onChange: (key: T) => void;
}) {
  return (
    <div className="scroll-thin -mx-4 mt-6 overflow-x-auto border-b border-slate-200 px-4 sm:mx-0 sm:px-0 dark:border-slate-800" role="tablist">
      <div className="flex gap-6">
        {items.map((item) => (
          <button key={item.key} type="button" role="tab" aria-selected={active === item.key} onClick={() => onChange(item.key)}
                  className={cx("relative whitespace-nowrap pb-3 text-sm font-medium transition-colors",
                    active === item.key ? "text-slate-900 dark:text-white"
                                        : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200")}>
            {item.label}
            {item.count != null && <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] dark:bg-slate-800">{item.count}</span>}
            {active === item.key && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-blue-600 dark:bg-blue-400" />}
          </button>
        ))}
      </div>
    </div>
  );
}

export function EmptyState({ title, text, children }: { title: string; text?: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-6 py-12 text-center dark:border-slate-800 dark:bg-slate-900/60">
      <p className="font-medium">{title}</p>
      {text && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{text}</p>}
      {children}
    </div>
  );
}

export function FileChip({ type, className }: { type: string; className?: string }) {
  const colors: Record<string, string> = {
    pdf: "bg-rose-50 text-rose-600 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30",
    docx: "bg-sky-50 text-sky-600 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30",
  };
  return (
    <span className={cx("grid size-10 shrink-0 place-items-center rounded-lg text-[10px] font-bold tracking-wide ring-1 ring-inset",
                        colors[type] ?? "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700", className)}>
      {type.toUpperCase().slice(0, 4)}
    </span>
  );
}
