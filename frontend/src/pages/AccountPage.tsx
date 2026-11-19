import { useState, type FormEvent, type ReactNode } from "react";

import { updateMe } from "../api/auth";
import { useAuth } from "../auth/useAuth";
import { ErrorMessage } from "../components/ErrorMessage";
import { Icon } from "../components/Icon";
import { ConfirmDialog } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { badge, button, card, cx, field, label, tone } from "../components/ui";
import { formatDate, formatRelative, initials } from "../lib/format";
import { toast } from "../lib/toast";

function Section({ title, text, danger = false, children }: { title: string; text: string; danger?: boolean; children: ReactNode }) {
  return (
    <section className={cx(card, "overflow-hidden", danger && "border-rose-200! dark:border-rose-500/30!")}>
      <div className="grid gap-4 p-5 sm:p-6 md:grid-cols-3">
        <div>
          <h2 className={cx("font-semibold", danger && "text-rose-700 dark:text-rose-400")}>{title}</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{text}</p>
        </div>
        <div className="md:col-span-2">{children}</div>
      </div>
    </section>
  );
}

/** Runs a form's submit with a busy state and an inline error. */
function useFormAction(action: (form: HTMLFormElement) => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await action(event.currentTarget);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, onSubmit };
}

export function AccountPage() {
  const { user, setUser, changePassword, logout, deleteAccount } = useAuth();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const nameForm = useFormAction(async (form) => {
    const name = String(new FormData(form).get("name")).trim();
    setUser(await updateMe(name));
    toast("Name saved.");
  });

  const passwordForm = useFormAction(async (form) => {
    const data = new FormData(form);
    const next = String(data.get("new"));
    if (next !== data.get("repeat")) throw new Error("The new passwords don't match.");
    await changePassword(String(data.get("current")), next);
    form.reset();
    toast("Password changed. Your other devices were logged out.");
  });

  if (!user) return null;
  const isAdmin = user.role === "admin";

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-5 px-4 py-6 sm:px-6 sm:py-10">
        <PageHeader title="Account" subtitle="Your profile, password and data." />

        <div className={cx(card, "flex flex-wrap items-center gap-4 p-5 sm:p-6")}>
          <div className="grid size-16 place-items-center rounded-full bg-blue-700 text-xl font-semibold text-white">
            {initials(user.name || user.email)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-lg font-semibold">{user.name || user.email.split("@")[0]}</p>
              <span className={cx(badge, isAdmin ? tone.violet : tone.gray)}>{isAdmin && <Icon name="shield" className="size-3" />}{isAdmin ? "Admin" : "User"}</span>
            </div>
            <p className="truncate text-sm text-slate-500 dark:text-slate-400">{user.email}</p>
          </div>
          <dl className="flex gap-6 text-sm">
            <div><dt className="text-xs text-slate-500 dark:text-slate-400">Member since</dt><dd className="font-medium">{formatDate(user.created_at)}</dd></div>
            <div><dt className="text-xs text-slate-500 dark:text-slate-400">Last login</dt><dd className="font-medium">{user.last_login_at ? formatRelative(user.last_login_at) : "–"}</dd></div>
          </dl>
        </div>

        <Section title="Name" text="Shown in the app. Your email can't be changed.">
          <form onSubmit={nameForm.onSubmit} className="space-y-3">
            <div className="flex flex-col gap-3 sm:flex-row">
              <input name="name" defaultValue={user.name} maxLength={100} className={field} aria-label="Name" placeholder="Your name" />
              <button type="submit" disabled={nameForm.busy} className={cx(button("primary"), "shrink-0")}>Save</button>
            </div>
            <ErrorMessage error={nameForm.error} />
          </form>
        </Section>

        <Section title="Password" text="Changing it logs you out on your other devices.">
          <form onSubmit={passwordForm.onSubmit} className="space-y-3">
            <div>
              <label className={label} htmlFor="current">Current password</label>
              <input id="current" name="current" type="password" required autoComplete="current-password" className={field} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className={label} htmlFor="new">New password</label>
                <input id="new" name="new" type="password" required minLength={8} maxLength={128} autoComplete="new-password" className={field} />
              </div>
              <div>
                <label className={label} htmlFor="repeat">Repeat new password</label>
                <input id="repeat" name="repeat" type="password" required maxLength={128} autoComplete="new-password" className={field} />
              </div>
            </div>
            <ErrorMessage error={passwordForm.error} />
            <div className="flex justify-end">
              <button type="submit" disabled={passwordForm.busy} className={button("primary")}>{passwordForm.busy ? "Saving…" : "Change password"}</button>
            </div>
          </form>
        </Section>

        <Section title="Log out" text="End the session on this device.">
          <button type="button" onClick={() => void logout()} className={button("secondary")}><Icon name="logout" className="size-4" /> Log out</button>
        </Section>

        <Section danger title="Delete account" text="Permanently removes your account, all your documents and all your chats. This can't be undone.">
          <button type="button" onClick={() => setConfirmDelete(true)} className={button("dangerOutline")}>
            <Icon name="trash" className="size-4" /> Delete my account
          </button>
        </Section>
      </div>

      {confirmDelete && (
        <ConfirmDialog title="Delete your account?" confirmLabel="Delete everything" onClose={() => setConfirmDelete(false)}
                       text="This permanently deletes your account with all your documents and chats."
                       onConfirm={async (form) => {
                         await deleteAccount(String(new FormData(form).get("password")));
                         toast("Your account and all its data were deleted.", "info");
                       }}>
          <div className="mt-5">
            <label className={label} htmlFor="delete-password">Enter your password to confirm</label>
            <input id="delete-password" name="password" type="password" required autoComplete="current-password" className={field} />
          </div>
        </ConfirmDialog>
      )}
    </div>
  );
}
