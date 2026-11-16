import type { Source } from "../api/types";

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** "just now", "5 min ago", "3 h ago", "yesterday", "4 days ago", then the date. */
export function formatRelative(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  const days = Math.floor(seconds / 86400);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return formatDate(iso);
}

export function formatSeconds(seconds: number | null | undefined): string {
  if (seconds == null) return "–";
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

/** "page 4" / "pages 4–6" / null */
export function pageLabel(source: Pick<Source, "page_number" | "page_end">): string | null {
  if (source.page_number == null) return null;
  if (source.page_end != null && source.page_end !== source.page_number) return `pages ${source.page_number}–${source.page_end}`;
  return `page ${source.page_number}`;
}

export function fileType(name: string): string {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

export function initials(nameOrEmail: string): string {
  const parts = nameOrEmail.split("@")[0].split(/[\s._-]+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] ?? "?").slice(0, 2)).toUpperCase();
}

/** "1 passage", "3 passages" */
export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function percent(value: number | null | undefined, digits = 0): string {
  return value == null ? "–" : `${(value * 100).toFixed(digits)}%`;
}
