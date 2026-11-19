import { useState, type ReactNode } from "react";

import { Icon } from "../../components/Icon";
import { APP_NAME, Logo } from "../../components/Logo";
import { cx, fieldBase, label } from "../../components/ui";

const POINTS = ["Answers only from your files, never made up", "Your documents stay private to your account",
                "PDF, DOCX and TXT up to 50 MB"];

/** The split page of login and register: a short pitch on the left (wide screens), the form on the right. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden p-12 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-slate-900" />
        <div className="absolute inset-y-0 right-0 w-1 bg-blue-500/70" />
        <div className="relative flex items-center gap-3"><Logo /><span className="text-lg font-semibold">{APP_NAME}</span></div>
        <div className="relative my-auto max-w-lg">
          <h2 className="text-4xl font-semibold leading-tight tracking-tight">
            Knowledge, made<br /><span className="text-blue-300">easy to search.</span>
          </h2>
          <p className="mt-4 text-slate-300">
            Upload PDFs, Word files and text. Ask questions in plain language and get answers built only from
            your files, with the exact pages to check.
          </p>
          <div className="mt-8 rounded-2xl border border-white/15 bg-white/10 p-4 shadow-2xl backdrop-blur" aria-hidden="true">
            <div className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md bg-white px-3.5 py-2 text-sm text-blue-900">
              Can I carry over unused vacation days?
            </div>
            <div className="mt-3 flex gap-2.5">
              <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-white/20"><Icon name="spark" className="size-4" /></div>
              <p className="text-sm leading-relaxed text-blue-50">
                Yes, up to <b>5 days</b>, used by March 31{" "}
                <span className="inline-flex h-[1.15rem] min-w-[1.3rem] items-center justify-center rounded-md bg-white/20 px-1 text-[11px] font-semibold">2</span>
              </p>
            </div>
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-white/10 px-3 py-2 text-xs text-blue-100">
              <Icon name="doc" className="size-4" /> Employee_Handbook.pdf · pages 14–15
            </div>
          </div>
          <ul className="mt-8 space-y-2.5 text-sm text-blue-100">
            {POINTS.map((point) => (
              <li key={point} className="flex items-center gap-2.5">
                <span className="grid size-5 place-items-center rounded-full bg-white/15"><Icon name="check" className="size-3.5" /></span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="fade-in w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden"><Logo /><span className="text-lg font-semibold">{APP_NAME}</span></div>
          {children}
        </div>
      </div>
    </div>
  );
}

export function PasswordField({ id, name, labelText, autoComplete, minLength, onValueChange }: {
  id: string;
  name: string;
  labelText: string;
  autoComplete: string;
  minLength?: number;
  onValueChange?: (value: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label className={label} htmlFor={id}>{labelText}</label>
      <div className="relative">
        <input id={id} name={name} type={visible ? "text" : "password"} autoComplete={autoComplete} required
               minLength={minLength} maxLength={128} className={`${fieldBase} py-2 pl-3 pr-10`}
               onChange={onValueChange ? (event) => onValueChange(event.target.value) : undefined} />
        <button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Hide password" : "Show password"}
                className="absolute inset-y-0 right-0 grid w-10 place-items-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
          <Icon name={visible ? "eyeoff" : "eye"} className="size-4" />
        </button>
      </div>
    </div>
  );
}

const STRENGTH = [
  ["Too short", "bg-rose-500"], ["Weak", "bg-rose-500"], ["Fair", "bg-amber-500"], ["Good", "bg-lime-500"], ["Strong", "bg-emerald-500"],
] as const;

/** A rough hint only; the backend's rule is 8 to 128 characters and not the email. */
export function StrengthMeter({ password }: { password: string }) {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score++;
  const level = password.length < 8 ? 0 : Math.max(1, score);
  const [word, color] = STRENGTH[level];
  return (
    <div aria-live="polite">
      <div className="mt-2 flex gap-1">
        {[1, 2, 3, 4].map((i) => <span key={i} className={cx("h-1 flex-1 rounded-full", i <= level ? color : "bg-slate-200 dark:bg-slate-800")} />)}
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        {password ? word : "8 to 128 characters"}{password && level < 3 ? " · longer is stronger" : ""}
      </p>
    </div>
  );
}
