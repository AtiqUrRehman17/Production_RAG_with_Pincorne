export function Spinner({ className = "size-5" }: { className?: string }) {
  return <span className={`${className} inline-block animate-spin rounded-full border-2 border-slate-300 border-t-blue-600 dark:border-slate-700 dark:border-t-blue-400`} />;
}

export function FullPageSpinner() {
  return (
    <div className="flex h-full min-h-48 items-center justify-center" role="status" aria-label="Loading">
      <Spinner className="size-8" />
    </div>
  );
}
