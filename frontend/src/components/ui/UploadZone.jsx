import { motion } from "framer-motion";
import { FileUp, UploadCloud } from "lucide-react";
import { cn } from "../../utils/cn";

export function UploadZone({
  onFileSelect,
  fileName,
  isDragging = false,
  className = "",
}) {
  return (
    <motion.label
      whileHover={{ y: -2, scale: 1.01 }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 px-8 py-10 text-center transition dark:border-slate-700 dark:bg-slate-900/60",
        isDragging
          ? "border-slate-900 bg-slate-100 dark:border-slate-300 dark:bg-slate-800"
          : "",
        className,
      )}
    >
      <input
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={onFileSelect}
      />
      <div className="mb-4 rounded-full bg-white p-3 shadow-sm dark:bg-slate-950">
        {fileName ? (
          <FileUp className="h-6 w-6 text-slate-900 dark:text-slate-100" />
        ) : (
          <UploadCloud className="h-6 w-6 text-slate-900 dark:text-slate-100" />
        )}
      </div>
      <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
        {fileName ? "Replace file" : "Drop your CSV here"}
      </p>
      <p className="mt-2 max-w-sm text-sm text-slate-600 dark:text-slate-400">
        Browse or drag a CSV file to begin validation.
      </p>
    </motion.label>
  );
}
