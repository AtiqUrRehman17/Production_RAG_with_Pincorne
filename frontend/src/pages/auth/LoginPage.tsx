import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, type Location } from "react-router";

import { useAuth } from "../../auth/useAuth";
import { ErrorMessage } from "../../components/ErrorMessage";
import { button, field, label, link } from "../../components/ui";
import { AuthLayout, PasswordField } from "./AuthLayout";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: Location } | null)?.from;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await login({ email: String(form.get("email")), password: String(form.get("password")) });
      navigate(from ? `${from.pathname}${from.search}` : "/", { replace: true });
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Log in to chat with your documents.</p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <div>
          <label className={label} htmlFor="email">Email</label>
          <input id="email" name="email" type="email" autoComplete="email" required autoFocus className={field} placeholder="you@company.com" />
        </div>
        <PasswordField id="password" name="password" labelText="Password" autoComplete="current-password" />
        <ErrorMessage error={error} />
        <button type="submit" disabled={busy} className={`${button("primary", "lg")} w-full`}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
        No account yet? <Link to="/register" className={link}>Create one</Link>
      </p>
    </AuthLayout>
  );
}
