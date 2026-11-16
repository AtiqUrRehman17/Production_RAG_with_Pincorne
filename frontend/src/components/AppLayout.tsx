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
    ["/documents", "Documents", "doc"],
    ...(user?.role === "admin" ? [["/admin", "Admin", "chart"] as NavItem] : []),
  ];
  const tabs: NavItem[] = [...items, ["/account", "Account", "user"]];

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="hidden w-[76px] shrink-0 flex-col items-center gap-2 border-r border-zinc-200 bg-white py-3
                        md:flex dark:border-zinc-800 dark:bg-zinc-950">
        <NavLink to="/chat" className="mb-3" title="RAG Documents"><Logo /></NavLink>
        {items.map(([path, label, icon]) => (
          <NavLink key={path} to={path} className={({ isActive }) => cx(
            "flex w-14 flex-col items-center gap-1 rounded-xl py-2 text-[10px] font-medium transition-colors",
            isActive ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                     : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100")}>
            <Icon name={icon} />{label}
          </NavLink>
        ))}
        <div className="mt-auto flex flex-col items-center gap-2">
          <button type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                  className="inline-grid size-10 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900
                             dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                  title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
            <Icon name={theme === "dark" ? "sun" : "moon"} />
          </button>
          <NavLink to="/account" title="Account" className={({ isActive }) => cx(
            "grid size-10 place-items-center rounded-full bg-linear-to-br from-amber-400 to-rose-500 text-xs font-semibold",
            "text-white ring-2 ring-offset-2 ring-offset-white dark:ring-offset-zinc-950", isActive ? "ring-indigo-500" : "ring-transparent")}>
            {initials(user?.name || user?.email || "?")}
          </NavLink>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1"><Outlet /></div>
        <nav className="pb-safe grid border-t border-zinc-200 bg-white/95 backdrop-blur md:hidden dark:border-zinc-800 dark:bg-zinc-950/95"
             style={{ gridTemplateColumns: `repeat(${tabs.length}, 1fr)` }}>
          {tabs.map(([path, label, icon]) => (
            <NavLink key={path} to={path} className={({ isActive }) => cx(
              "flex flex-col items-center gap-0.5 py-1.5 text-[11px] font-medium",
              isActive ? "text-indigo-600 dark:text-indigo-400" : "text-zinc-500 dark:text-zinc-400")}>
              <Icon name={icon} className="size-6" />{label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
