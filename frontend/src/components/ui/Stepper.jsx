import { Check } from "lucide-react";
import { workflowSteps } from "../../constants/importTypes";
import { cn } from "../../utils/cn";

export function Stepper({ currentStep, steps = workflowSteps }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-full border border-slate-200 bg-slate-50/80 p-2 dark:border-slate-800 dark:bg-slate-900/70">
      {steps.map((step, index) => {
        const isActive = index + 1 === currentStep;
        const isComplete = index + 1 < currentStep;

        return (
          <div key={step} className="flex items-center gap-2 text-sm">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full border",
                isComplete
                  ? "border-emerald-600 bg-emerald-600 text-white"
                  : isActive
                    ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                    : "border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400",
              )}
            >
              {isComplete ? <Check size={16} /> : index + 1}
            </div>
            <span
              className={cn(
                "font-medium",
                isActive || isComplete
                  ? "text-slate-900 dark:text-slate-100"
                  : "text-slate-500 dark:text-slate-400",
              )}
            >
              {step}
            </span>
          </div>
        );
      })}
    </div>
  );
}
