import { NavLink, Outlet } from "react-router";

import { useAuth } from "../auth/useAuth";
import { initials } from "../lib/format";
import { useTheme } from "../lib/theme";
import { Icon, type IconName } from "./Icon";
import { Logo } from "./Logo";
import { cx } from "./ui";

type NavItem = [path: string, label: string, icon: IconName];

/** The frame of every logged-in page: an icon rail on desktop, a tab bar on phones. */
export function AppLayout() {
  const { user } = useAuth();
  const [theme, setTheme] = useTheme();
  const items: NavItem[] = [
    ["/chat", "Chat", "chat"],
    ["/documents", "Docs", "doc"],
    ...(user?.role === "admin" ? [["/admin", "Admin", "chart"] as NavItem] : []),
  ];
  const tabs: NavItem[] = [...items, ["/account", "Account", "user"]];

  return (
    <div className="flex h-dvh overflow-hidden bg-white dark:bg-slate-950">
      <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-slate-200 bg-white px-3 py-5 md:flex dark:border-slate-800 dark:bg-slate-950">
        <NavLink to="/chat" className="flex items-center gap-3 px-2" title="RAG Documents Home">
          <Logo size="md" />
          <span className="text-sm font-semibold tracking-tight text-slate-900 dark:text-white">RAG Documents</span>
        </NavLink>

        <div className="flex w-full flex-col gap-1">
          {items.map(([path, label, icon]) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                cx(
                  "group relative flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-blue-50 text-blue-800 dark:bg-blue-950/50 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-r-full bg-blue-700 dark:bg-blue-400" />
                  )}
                  <Icon name={icon} className="size-[18px] shrink-0" />
                  <span>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>

        <div className="mt-auto flex items-center justify-between border-t border-slate-200 pt-4 dark:border-slate-800">
          <button
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="grid size-10 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100"
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} className="size-5" />
          </button>

          <NavLink
            to="/account"
            title="Account Settings"
            className={({ isActive }) =>
              cx(
                "relative grid size-10 place-items-center rounded-full bg-blue-700 text-xs font-semibold text-white transition hover:bg-blue-800 ring-2 ring-offset-2 ring-offset-white dark:ring-offset-slate-950",
                isActive ? "ring-blue-600" : "ring-transparent"
              )
            }
          >
            {initials(user?.name || user?.email || "?")}
          </NavLink>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1">
          <Outlet />
        </div>
        <nav
          className="pb-safe grid border-t border-slate-200 bg-white/95 backdrop-blur md:hidden dark:border-slate-800 dark:bg-slate-950/95"
          style={{ gridTemplateColumns: `repeat(${tabs.length}, 1fr)` }}
        >
          {tabs.map(([path, label, icon]) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                cx(
                  "flex flex-col items-center gap-0.5 py-2 text-[10px] font-semibold uppercase tracking-wider",
                  isActive
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-slate-500 dark:text-slate-400"
                )
              }
            >
              <Icon name={icon} className="size-5" />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
