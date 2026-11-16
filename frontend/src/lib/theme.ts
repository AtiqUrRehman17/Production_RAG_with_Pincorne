// Light or dark. The user's choice is remembered in this browser; without one the system setting is used.
import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const KEY = "rag-theme";
const media = matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function current(): Theme {
  return stored() ?? (media.matches ? "dark" : "light");
}

function apply(): void {
  document.documentElement.classList.toggle("dark", current() === "dark");
  listeners.forEach((listener) => listener());
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // storage blocked: the choice lasts until the page is reloaded
  }
  apply();
}

media.addEventListener("change", apply);
apply();

export function useTheme(): [Theme, (theme: Theme) => void] {
  const theme = useSyncExternalStore((listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }, current);
  return [theme, setTheme];
}
