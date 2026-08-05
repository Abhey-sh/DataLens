import { cn } from "../../utils/cn";

export function Input({ className = "", ...props }) {
  return (
    <input
      className={cn(
        "w-full rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-700 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-slate-600 dark:focus:ring-slate-900",
        className,
      )}
      {...props}
    />
  );
}
