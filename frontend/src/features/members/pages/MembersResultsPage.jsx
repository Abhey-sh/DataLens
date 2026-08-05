import { motion } from "framer-motion";
import {
  CheckCircle2,
  Download,
  FileText,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Stepper } from "../../../components/ui/Stepper";
import {
  downloadAudit,
  downloadCorrected,
  downloadSummary,
  getApiErrorMessage,
  getValidationResult,
} from "../services/validationService";

export function MembersResultsPage() {
  const result = useMemo(() => getValidationResult(), []);
  const [downloading, setDownloading] = useState("");
  const [error, setError] = useState("");

  if (!result) {
    return <Navigate to="/single-upload/members/upload" replace />;
  }

  const stats = [
    { label: "Records", value: result.summary.totalRecords, tone: "info" },
    { label: "Valid", value: result.summary.valid, tone: "success" },
  ];
  const reports = [
    ["Summary", downloadSummary],
    ["Audit", downloadAudit],
    ["Corrected Dataset", downloadCorrected],
  ];

  const handleDownload = async (name, download) => {
    setDownloading(name);
    setError("");
    try {
      await download("csv");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Download failed"));
    } finally {
      setDownloading("");
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
            Results
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-slate-50">
            Validation complete
          </h1>
        </div>
        <Stepper currentStep={4} />
      </div>

      <Card className="overflow-hidden">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300">
                <CheckCircle2 size={24} />
              </div>
              <Badge tone="success">Validation completed</Badge>
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-slate-950 dark:text-slate-50">
                Your dataset is ready to review and export.
              </h2>
              <p className="mt-3 text-slate-600 dark:text-slate-400">
                The validation run generated a corrected CSV, an audit trail,
                and a summary artifact for downstream teams.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              {reports.map(([name, download]) => (
                <Button
                  key={name}
                  className="gap-2"
                  disabled={Boolean(downloading)}
                  onClick={() => handleDownload(name, download)}
                >
                  <Download size={16} />
                  {downloading === name ? "Downloading..." : name}
                </Button>
              ))}
              <Link to="/single-upload">
                <Button variant="secondary">Run again</Button>
              </Link>
            </div>
            {error ? <p className="text-sm text-rose-300">{error}</p> : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {stats.map((stat) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-3xl border border-slate-200 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-900/60"
              >
                <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400">
                  <FileText size={15} />
                  {stat.label}
                </div>
                <div className="mt-4 text-3xl font-semibold text-slate-950 dark:text-slate-50">
                  {stat.value}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </Card>

      <Card className="flex flex-col gap-4 border-slate-200/80 bg-slate-900 text-white dark:border-slate-700 dark:bg-slate-950">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-white/10 p-2.5">
            <Sparkles size={18} />
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-slate-400">
              Next step
            </p>
            <h3 className="text-xl font-semibold">
              Continue with your downstream import workflow.
            </h3>
          </div>
        </div>
        <p className="max-w-3xl text-sm leading-7 text-slate-300">
          The generated files can be shared with analysts, data operations, and
          engineering teams once you have reviewed the validation outcomes.
        </p>
      </Card>
    </div>
  );
}
