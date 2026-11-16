// 24px outline icons, drawn with the current text colour
const PATHS = {
  chat: "M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H9l-5 4z",
  doc: "M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M14 3v5h5 M9 13h6 M9 17h4",
  chart: "M4 20h16 M7 16v-5 M12 16V6 M17 16v-8",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4.5 20.5a7.5 7.5 0 0 1 15 0",
  plus: "M12 5v14 M5 12h14",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  x: "M6 6l12 12 M18 6 6 18",
  send: "M12 19V5 M6 11l6-6 6 6",
  stop: "M8 8h8v8H8z",
  thumb: "M7 11v9H4v-9z M7 11l4-7.5c1.4 0 2.5 1.1 2.5 2.5v3h5a2 2 0 0 1 2 2.3l-1.1 6.5a2 2 0 0 1-2 1.7H7",
  copy: "M9 9h10v10a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V11a2 2 0 0 1 2-2z M15 9V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2",
  trash: "M4 7h16 M10 11v6 M14 11v6 M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12 M9 7V4h6v3",
  upload: "M12 15V4 M7 9l5-5 5 5 M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-3.5-3.5",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4",
  moon: "M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11z",
  logout: "M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3 M16 8l4 4-4 4 M20 12H10",
  check: "M5 12.5l4.5 4.5L19 7.5",
  alert: "M12 9v4 M12 17h.01 M10.3 4 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0z",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 11v5 M12 8h.01",
  external: "M14 4h6v6 M20 4l-9 9 M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4",
  chevron: "M9 6l6 6-6 6",
  down: "M6 9l6 6 6-6",
  layers: "M12 3l9 5-9 5-9-5z M3 13l9 5 9-5",
  pencil: "M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z M13.5 6.5l4 4",
  play: "M7 4.5v15l12-7.5z",
  refresh: "M20 12a8 8 0 1 1-2.3-5.6 M20 4v5h-5",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  eyeoff: "M3 3l18 18 M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3 3.9 M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.6 9.6 0 0 0 5.4-1.6 M9.9 9.9a3 3 0 0 0 4.2 4.2",
  spark: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2",
  list: "M9 6h11 M9 12h11 M9 18h11 M4.5 6h.01 M4.5 12h.01 M4.5 18h.01",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z M9 12l2 2 4-4",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "size-5" }: { name: IconName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
