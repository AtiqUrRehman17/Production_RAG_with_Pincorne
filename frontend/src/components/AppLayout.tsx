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
    <div className="flex h-dvh overflow-hidden bg-white dark:bg-zinc-950">
      <aside className="hidden w-[72px] shrink-0 flex-col items-center gap-2 border-r border-zinc-200/90 bg-zinc-50/80 py-3.5 backdrop-blur-md md:flex dark:border-zinc-800/90 dark:bg-zinc-950">
        <NavLink to="/chat" className="mb-4 transition-transform hover:scale-105" title="RAG Documents Home">
          <Logo size="md" />
        </NavLink>

        <div className="flex w-full flex-col items-center gap-1.5 px-2">
          {items.map(([path, label, icon]) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                cx(
                  "group relative flex w-13 flex-col items-center gap-1 rounded-xl py-2.5 text-[10px] font-semibold tracking-wide transition-all",
                  isActive
                    ? "bg-white text-indigo-600 shadow-xs ring-1 ring-zinc-200 dark:bg-zinc-900 dark:text-indigo-400 dark:ring-zinc-800"
                    : "text-zinc-500 hover:bg-zinc-200/60 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute -left-2 top-2 bottom-2 w-1 rounded-r-full bg-indigo-600 dark:bg-indigo-500" />
                  )}
                  <Icon name={icon} className="size-5 transition-transform group-hover:scale-110" />
                  <span>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>

        <div className="mt-auto flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="grid size-10 place-items-center rounded-xl text-zinc-500 transition hover:bg-zinc-200/60 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} className="size-5" />
          </button>

          <NavLink
            to="/account"
            title="Account Settings"
            className={({ isActive }) =>
              cx(
                "relative grid size-10 place-items-center rounded-full bg-linear-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white shadow-xs transition hover:opacity-90 ring-2 ring-offset-2 ring-offset-zinc-50 dark:ring-offset-zinc-950",
                isActive ? "ring-indigo-600" : "ring-transparent"
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
          className="pb-safe grid border-t border-zinc-200 bg-white/95 backdrop-blur md:hidden dark:border-zinc-800 dark:bg-zinc-950/95"
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
                    ? "text-indigo-600 dark:text-indigo-400"
                    : "text-zinc-500 dark:text-zinc-400"
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
