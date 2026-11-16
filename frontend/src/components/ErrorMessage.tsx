import { ApiError } from "../api/client";
import { Icon } from "./Icon";

/** A failed call's message, with the request ID to look up in the admin logs. */
export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div role="alert" className="fade-in flex gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800
                                 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
      <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">
        <p>{message}</p>
        {requestId && <p className="mt-1 font-mono text-[11px] opacity-70">Request ID: {requestId}</p>}
      </div>
    </div>
  );
}
