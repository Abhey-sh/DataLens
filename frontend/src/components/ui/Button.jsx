import { motion } from "framer-motion";
import { cn } from "../../utils/cn";

const variants = {
  primary:
    "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-slate-200",
  secondary:
    "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700",
  ghost:
    "bg-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
};

export function Button({
  children,
  className = "",
  variant = "primary",
  disabled = false,
  ...props
}) {
  return (
    <motion.button
      whileHover={!disabled ? { y: -1, scale: 1.01 } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
      type="button"
      disabled={disabled}
      className={cn(
        "inline-flex items-center justify-center rounded-full px-4 py-2.5 text-sm font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:focus:ring-slate-700",
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </motion.button>
  );
}
