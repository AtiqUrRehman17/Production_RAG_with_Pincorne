import { useSyncExternalStore } from "react";

import { dismissToast, getToasts, subscribeToasts } from "../lib/toast";
import { Icon } from "./Icon";

const styles = {
  success: ["check", "text-emerald-500"],
  error: ["alert", "text-rose-500"],
  info: ["info", "text-indigo-500"],
} as const;

export function Toaster() {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts);
  return (
    <div className="pointer-events-none fixed inset-x-0 top-3 z-[70] flex flex-col items-center gap-2 px-3" aria-live="polite">
      {toasts.map((item) => {
        const [icon, color] = styles[item.kind];
        return (
          <div key={item.id} role={item.kind === "error" ? "alert" : "status"}
               className="fade-in pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border border-zinc-200
                          bg-white px-3.5 py-2.5 text-sm shadow-lg sm:w-auto dark:border-zinc-700 dark:bg-zinc-900">
            <span className={`mt-0.5 ${color}`}><Icon name={icon} className="size-4" /></span>
            <span className="flex-1">{item.message}</span>
            <button type="button" onClick={() => dismissToast(item.id)} className="-mr-1 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                    aria-label="Dismiss"><Icon name="x" className="size-4" /></button>
          </div>
        );
      })}
    </div>
  );
}
