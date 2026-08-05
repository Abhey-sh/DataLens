import { CheckCircle2, CloudUpload, Database } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import { getValidationResult } from "../services/validationService";

function percentage(value, total) {
  return total ? `${((value / total) * 100).toFixed(2)}% of total` : "0% of total";
}

export function MembersReviewPage() {
  const navigate = useNavigate();
  const [result] = useState(() => getValidationResult());

  useEffect(() => {
    if (!result) {
      navigate("/single-upload/members/upload", { replace: true });
    }
  }, [navigate, result]);

  if (!result) return null;

  const summary = result.summary;

  const summaryCards = [
    {
      label: "Total Records",
      value: summary.totalRecords,
      caption: "100% of file",
      icon: Database,
      style: "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900",
      valueStyle: "text-slate-950 dark:text-white",
      iconStyle: "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50",
    },
    {
      label: "Valid Records",
      value: summary.valid,
      caption: percentage(summary.valid, summary.totalRecords),
      icon: CheckCircle2,
      style:
        "border-emerald-200 bg-emerald-50/70 dark:border-emerald-900/50 dark:bg-emerald-950/20",
      valueStyle: "text-emerald-700 dark:text-emerald-400",
      iconStyle: "bg-white/80 text-emerald-600 dark:bg-emerald-950",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500">
            Single Upload <span className="mx-2">›</span> Members
          </p>
          <h1 className="mt-3 text-2xl font-semibold text-slate-950 dark:text-white">
            Review Members Data
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Confirm the validated dataset before finalizing the import.
          </p>
        </div>
        <Button
          variant="secondary"
          className="gap-2"
          onClick={() => navigate("/single-upload/members/upload")}
        >
          <CloudUpload size={16} />
          Upload New File
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className={`flex min-h-32 items-start justify-between rounded-2xl border p-5 shadow-sm ${card.style}`}
          >
            <div>
              <p className="text-xs font-medium text-slate-500">{card.label}</p>
              <p className={`mt-2 text-3xl font-semibold ${card.valueStyle}`}>
                {card.value.toLocaleString()}
              </p>
              <p className="mt-2 text-xs text-slate-500">{card.caption}</p>
            </div>
            <span className={`rounded-lg p-2 ${card.iconStyle}`}>
              <card.icon size={18} />
            </span>
          </div>
        ))}
      </div>

      <Button
        className="w-full bg-indigo-700 hover:bg-indigo-600 sm:w-auto dark:bg-indigo-600 dark:text-white"
        onClick={() => navigate("/single-upload/members/results")}
      >
        Finalize Review & Continue
      </Button>
    </div>
  );
}
