import { Link } from "react-router";

import { Logo } from "../components/Logo";
import { button } from "../components/ui";

export function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <Logo size="lg" />
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">The page you were looking for doesn't exist.</p>
      <Link to="/" className={button("primary")}>Go to the app</Link>
    </div>
  );
}
