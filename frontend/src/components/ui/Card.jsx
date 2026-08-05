import { motion } from "framer-motion";
import { cn } from "../../utils/cn";

export function Card({ children, className = "", hover = false, ...props }) {
  return (
    <motion.div
      layout
      whileHover={hover ? { y: -2, scale: 1.01 } : undefined}
      className={cn(
        "rounded-3xl border border-slate-200/80 bg-white/90 p-6 shadow-[0_10px_40px_-20px_rgba(15,23,42,0.25)] backdrop-blur dark:border-slate-800 dark:bg-slate-900/80",
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
