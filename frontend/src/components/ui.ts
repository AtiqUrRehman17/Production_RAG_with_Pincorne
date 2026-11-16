// Shared class names, so buttons, fields and cards look the same everywhere

const buttonBase = "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors "
  + "disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60";

const buttonVariants = {
  primary: "bg-indigo-600 text-white shadow-sm hover:bg-indigo-500",
  secondary: "border border-zinc-200 bg-white text-zinc-800 hover:bg-zinc-50 "
    + "dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800",
  ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
  danger: "bg-rose-600 text-white shadow-sm hover:bg-rose-500",
  dangerOutline: "border border-rose-200 bg-white text-rose-700 hover:bg-rose-50 "
    + "dark:border-rose-500/30 dark:bg-zinc-900 dark:text-rose-400 dark:hover:bg-rose-500/10",
};

const buttonSizes = { sm: "px-2.5 py-1.5 text-xs", md: "px-3.5 py-2 text-sm", lg: "px-3.5 py-2.5 text-sm" };

export function button(variant: keyof typeof buttonVariants = "secondary", size: keyof typeof buttonSizes = "md"): string {
  return `${buttonBase} ${buttonSizes[size]} ${buttonVariants[variant]}`;
}

export const iconButton = "inline-grid size-8 shrink-0 place-items-center rounded-lg text-zinc-500 transition-colors "
  + "hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100 "
  + "disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60";

// A text field without padding; add px-3 py-2, or pl-9 pr-3 py-2 next to an icon
export const fieldBase = "block w-full rounded-lg border border-zinc-300 bg-white text-sm outline-none "
  + "placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 "
  + "dark:border-zinc-700 dark:bg-zinc-900 dark:focus:border-indigo-400 disabled:opacity-60";
export const field = `${fieldBase} px-3 py-2`;
export const select = "rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500 "
  + "focus:ring-4 focus:ring-indigo-500/15 dark:border-zinc-700 dark:bg-zinc-900";

export const label = "mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300";
export const card = "rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/60";
export const muted = "text-zinc-500 dark:text-zinc-400";
export const badge = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium";
export const link = "font-medium text-indigo-600 hover:underline dark:text-indigo-400";

export const tone = {
  green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
  red: "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  indigo: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300",
  violet: "bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300",
  gray: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
};

// A citation number: [1]. citeChip is the clickable one in answers, citeBadge just shows the number.
const citeBase = "inline-flex h-[1.15rem] min-w-[1.3rem] shrink-0 items-center justify-center rounded-md px-1 text-[11px] font-semibold";
export const citeBadge = `${citeBase} bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300`;
export const citeChip = `${citeBase} mx-0.5 align-[1px] transition-colors bg-indigo-100 text-indigo-700 hover:bg-indigo-600 `
  + "hover:text-white dark:bg-indigo-500/20 dark:text-indigo-300 dark:hover:bg-indigo-500 dark:hover:text-white";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
