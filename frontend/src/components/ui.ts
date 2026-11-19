// Shared class names, so buttons, fields and cards look the same everywhere

const buttonBase = "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors "
  + "disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60";

const buttonVariants = {
  primary: "bg-blue-700 text-white shadow-sm hover:bg-blue-800",
  secondary: "border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 "
    + "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100",
  danger: "bg-rose-600 text-white shadow-sm hover:bg-rose-500",
  dangerOutline: "border border-rose-200 bg-white text-rose-700 hover:bg-rose-50 "
    + "dark:border-rose-500/30 dark:bg-slate-900 dark:text-rose-400 dark:hover:bg-rose-500/10",
};

const buttonSizes = { sm: "px-2.5 py-1.5 text-xs", md: "px-3.5 py-2 text-sm", lg: "px-3.5 py-2.5 text-sm" };

export function button(variant: keyof typeof buttonVariants = "secondary", size: keyof typeof buttonSizes = "md"): string {
  return `${buttonBase} ${buttonSizes[size]} ${buttonVariants[variant]}`;
}

export const iconButton = "inline-grid size-8 shrink-0 place-items-center rounded-lg text-slate-500 transition-colors "
  + "hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100 "
  + "disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60";

// A text field without padding; add px-3 py-2, or pl-9 pr-3 py-2 next to an icon
export const fieldBase = "block w-full rounded-lg border border-slate-300 bg-white text-sm outline-none "
  + "placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/15 "
  + "dark:border-slate-700 dark:bg-slate-900 dark:focus:border-blue-400 disabled:opacity-60";
export const field = `${fieldBase} px-3 py-2`;
export const select = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 "
  + "focus:ring-4 focus:ring-blue-500/15 dark:border-slate-700 dark:bg-slate-900";

export const label = "mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300";
export const card = "rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/60";
export const muted = "text-slate-500 dark:text-slate-400";
export const badge = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium";
export const link = "font-medium text-blue-600 hover:underline dark:text-blue-400";

export const tone = {
  green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
  red: "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  indigo: "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300",
  violet: "bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300",
  gray: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

// A citation number: [1]. citeChip is the clickable one in answers, citeBadge just shows the number.
const citeBase = "inline-flex h-[1.15rem] min-w-[1.3rem] shrink-0 items-center justify-center rounded-md px-1 text-[11px] font-semibold";
export const citeBadge = `${citeBase} bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300`;
export const citeChip = `${citeBase} mx-0.5 align-[1px] transition-colors bg-blue-100 text-blue-700 hover:bg-blue-600 `
  + "hover:text-white dark:bg-blue-500/20 dark:text-blue-300 dark:hover:bg-blue-500 dark:hover:text-white";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
