import { useSyncExternalStore } from "react";

import { dismissToast, getToasts, subscribeToasts } from "../lib/toast";
import { Icon } from "./Icon";

const styles = {
  success: ["check", "text-emerald-500"],
  error: ["alert", "text-rose-500"],
  info: ["info", "text-blue-500"],
} as const;

export function Toaster() {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts);
  return (
    <div className="pointer-events-none fixed inset-x-0 top-3 z-[70] flex flex-col items-center gap-2 px-3" aria-live="polite">
      {toasts.map((item) => {
        const [icon, color] = styles[item.kind];
        return (
          <div key={item.id} role={item.kind === "error" ? "alert" : "status"}
               className="fade-in pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border border-slate-200
                          bg-white px-3.5 py-2.5 text-sm shadow-lg sm:w-auto dark:border-slate-700 dark:bg-slate-900">
            <span className={`mt-0.5 ${color}`}><Icon name={icon} className="size-4" /></span>
            <span className="flex-1">{item.message}</span>
            <button type="button" onClick={() => dismissToast(item.id)} className="-mr-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                    aria-label="Dismiss"><Icon name="x" className="size-4" /></button>
          </div>
        );
      })}
    </div>
  );
}
