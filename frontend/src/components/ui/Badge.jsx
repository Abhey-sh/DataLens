import { cn } from "../../utils/cn";

export function Badge({ children, className = "", tone = "default" }) {
  const tones = {
    default:
      "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
    success:
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    warning:
      "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    danger: "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
    info: "bg-sky-50 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
