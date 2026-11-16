import { Icon } from "./Icon";

export const APP_NAME = "RAG Documents";

const sizes = {
  sm: ["size-8", "size-4"],
  md: ["size-9", "size-5"],
  lg: ["size-14", "size-7"],
} as const;

export function Logo({ size = "md" }: { size?: keyof typeof sizes }) {
  const [box, icon] = sizes[size];
  return (
    <div className={`${box} grid shrink-0 place-items-center rounded-xl bg-linear-to-br from-indigo-500 via-indigo-600
                     to-violet-600 text-white shadow-sm shadow-indigo-600/30`}>
      <Icon name="spark" className={icon} />
    </div>
  );
}
