export function Spinner({ className = "size-5" }: { className?: string }) {
  return <span className={`${className} inline-block animate-spin rounded-full border-2 border-zinc-300 border-t-indigo-600 dark:border-zinc-700 dark:border-t-indigo-400`} />;
}

export function FullPageSpinner() {
  return (
    <div className="flex h-full min-h-48 items-center justify-center" role="status" aria-label="Loading">
      <Spinner className="size-8" />
    </div>
  );
}
