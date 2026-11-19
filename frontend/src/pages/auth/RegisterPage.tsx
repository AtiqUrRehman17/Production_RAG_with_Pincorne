import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../../auth/useAuth";
import { ErrorMessage } from "../../components/ErrorMessage";
import { button, field, label, link } from "../../components/ui";
import { toast } from "../../lib/toast";
import { AuthLayout, PasswordField, StrengthMeter } from "./AuthLayout";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const tokens = await register({
        name: String(form.get("name")).trim(),
        email: String(form.get("email")),
        password: String(form.get("password")),
      });
      if (tokens.transfer_job_id) {
        toast("Account created. The documents and chats made before accounts existed are being moved to it.", "info", 8);
        navigate("/chat", { replace: true });
      } else {
        toast("Account created. Upload a document to begin.");
        navigate("/documents", { replace: true });
      }
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Your documents stay private to you.</p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <div>
          <label className={label} htmlFor="name">Name <span className="font-normal text-slate-400">(optional)</span></label>
          <input id="name" name="name" autoComplete="name" maxLength={100} autoFocus className={field} placeholder="Sam Carter" />
        </div>
        <div>
          <label className={label} htmlFor="email">Email</label>
          <input id="email" name="email" type="email" autoComplete="email" required className={field} placeholder="you@company.com" />
        </div>
        <div>
          <PasswordField id="password" name="password" labelText="Password" autoComplete="new-password" minLength={8}
                         onValueChange={setPassword} />
          <StrengthMeter password={password} />
        </div>
        <ErrorMessage error={error} />
        <button type="submit" disabled={busy} className={`${button("primary", "lg")} w-full`}>{busy ? "Creating your account…" : "Create account"}</button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
        Already registered? <Link to="/login" className={link}>Log in</Link>
      </p>
    </AuthLayout>
  );
}
