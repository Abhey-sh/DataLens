import { motion } from "framer-motion";
import {
  CheckCircle2,
  Download,
  FileText,
  ImageIcon,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Stepper } from "../../../components/ui/Stepper";
import { assetsWorkflowSteps } from "../../../constants/importTypes";
import {
  downloadAudit,
  downloadCorrected,
  downloadRemoved,
  downloadSummary,
  getApiErrorMessage,
  getValidationResult,
} from "../services/validationService";

function displayRowNumber(rowNumber) {
  return rowNumber > 0 ? rowNumber + 1 : rowNumber;
}

export function AssetsResultsPage() {
  const result = useMemo(() => getValidationResult(), []);
  const [downloading, setDownloading] = useState("");
  const [error, setError] = useState("");

  const removedRows = useMemo(() => {
    const rows = (result?.affectedRows ?? []).filter(
      (issue) => issue.rowNumber > 0 && issue.status === "Removed",
    );
    // One entry per original row.
    const byRow = new Map();
    for (const issue of rows) {
      if (!byRow.has(issue.rowNumber)) {
        byRow.set(issue.rowNumber, issue);
      }
    }
    return Array.from(byRow.values()).sort(
      (left, right) => left.rowNumber - right.rowNumber,
    );
  }, [result]);

  if (!result) {
    return <Navigate to="/single-upload/assets/upload" replace />;
  }

  const headerBlocked = result.affectedRows?.some(
    (issue) => issue.ruleId === "required_headers",
  );
  if (headerBlocked) {
    return <Navigate to="/single-upload/assets/upload" replace />;
  }

  const removedCount = removedRows.length;

  const stats = [
    {
      label: "Uploaded rows",
      value: result.summary.totalRecords,
      icon: FileText,
    },
    {
      label: "Kept rows",
      value: result.summary.valid,
      icon: CheckCircle2,
    },
    {
      label: "Removed rows",
      value: removedCount,
      icon: Trash2,
    },
    {
      label: "Score",
      value: `${result.summary.validationScore}%`,
      icon: ImageIcon,
    },
  ];

  const reports = [
    ["Summary", downloadSummary],
    ["Audit", downloadAudit],
    ["Corrected Dataset", downloadCorrected],
    ["Removed Rows", downloadRemoved],
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
    <div className="relative isolate -mx-4 -my-6 min-h-[calc(100vh-4rem)] overflow-hidden px-4 py-6 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_12%_0%,rgba(14,165,233,0.12),transparent_32%),radial-gradient(circle_at_88%_10%,rgba(16,185,129,0.12),transparent_30%),linear-gradient(180deg,#f8fafc_0%,#ffffff_55%,#f1f5f9_100%)] dark:bg-[radial-gradient(circle_at_12%_0%,rgba(14,165,233,0.14),transparent_32%),radial-gradient(circle_at_88%_10%,rgba(16,185,129,0.12),transparent_30%),linear-gradient(180deg,#0b1220_0%,#0f172a_60%,#111827_100%)]" />

      <div className="mx-auto max-w-[1400px] space-y-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200/70 bg-emerald-50/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
              Finalize
            </div>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 dark:text-white sm:text-4xl">
              Assets validation complete
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-400">
              Download the cleaned file, or the removed-rows CSV to see exactly
              which records were dropped and why.
            </p>
          </div>
          <Stepper currentStep={3} steps={assetsWorkflowSteps} />
        </div>

        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          className="overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/90 shadow-[0_28px_80px_-40px_rgba(15,23,42,0.45)] backdrop-blur-xl dark:border-slate-800 dark:bg-slate-950/75"
        >
          <div className="grid gap-8 p-6 lg:grid-cols-[1.15fr_0.85fr] lg:items-center sm:p-8">
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300">
                  <CheckCircle2 size={24} />
                </div>
                <Badge tone="success">Ready to download</Badge>
              </div>
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-950 dark:text-slate-50">
                  Cleaned assets file is ready
                </h2>
                <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">
                  Non-primary studio rows, resource types, image URLs, and
                  duplicate resource IDs were removed automatically.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                {reports.map(([name, download]) => (
                  <Button
                    key={name}
                    className="gap-2"
                    variant={name === "Removed Rows" ? "secondary" : "primary"}
                    disabled={
                      Boolean(downloading) ||
                      (name === "Removed Rows" && removedCount === 0)
                    }
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
              {error ? (
                <p className="text-sm text-rose-500">{error}</p>
              ) : null}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {stats.map((stat, index) => {
                const Icon = stat.icon;
                return (
                  <motion.div
                    key={stat.label}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 * index }}
                    className="rounded-3xl border border-slate-200/80 bg-slate-50/80 p-4 dark:border-slate-800 dark:bg-slate-900/60"
                  >
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400">
                      <Icon
                        size={15}
                        className="text-teal-600 dark:text-teal-300"
                      />
                      {stat.label}
                    </div>
                    <div className="mt-4 text-3xl font-bold tracking-tight text-slate-950 dark:text-slate-50">
                      {stat.value}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.06 }}
          className="rounded-[28px] border border-slate-200/80 bg-white/90 p-6 dark:border-slate-800 dark:bg-slate-950/75"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
                Removed rows
              </h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {removedCount
                  ? `${removedCount.toLocaleString()} full row${
                      removedCount === 1 ? "" : "s"
                    } dropped during validation.`
                  : "No rows were removed in this run."}
              </p>
            </div>
            <Button
              variant="secondary"
              className="gap-2"
              disabled={removedCount === 0 || Boolean(downloading)}
              onClick={() => handleDownload("Removed Rows", downloadRemoved)}
            >
              <Download size={16} />
              Download removed rows
            </Button>
          </div>

          {removedCount ? (
            <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-[0.14em] text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Row</th>
                    <th className="px-4 py-3 font-semibold">Resource ID</th>
                    <th className="px-4 py-3 font-semibold">Studio</th>
                    <th className="px-4 py-3 font-semibold">Type</th>
                    <th className="px-4 py-3 font-semibold">Rule</th>
                    <th className="px-4 py-3 font-semibold">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {removedRows.slice(0, 50).map((row) => (
                    <tr
                      key={`${row.rowNumber}-${row.ruleId}`}
                      className="border-t border-slate-100 dark:border-slate-800"
                    >
                      <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                        {displayRowNumber(row.rowNumber)}
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {row.memberId ||
                          row.rowData?.resourceForeignId ||
                          "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {row.rowData?.studioForeignId || "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {row.rowData?.resourceType || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone="warning">{row.ruleName}</Badge>
                      </td>
                      <td className="max-w-md px-4 py-3 text-slate-600 dark:text-slate-400">
                        {row.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {removedCount > 50 ? (
                <div className="border-t border-slate-100 px-4 py-3 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  Showing first 50 of {removedCount.toLocaleString()}. Download
                  the CSV for the full list.
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
              All uploaded rows passed assets cleanup rules.
            </div>
          )}
        </motion.section>

        {result.businessRules?.length ? (
          <motion.section
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="rounded-[28px] border border-slate-200/80 bg-white/90 p-6 dark:border-slate-800 dark:bg-slate-950/75"
          >
            <h3 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
              Cleanup summary
            </h3>
            <div className="mt-4 space-y-2">
              {result.businessRules.map((rule) => (
                <div
                  key={rule.ruleId}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200/80 px-4 py-3 text-sm dark:border-slate-800"
                >
                  <div>
                    <p className="font-medium text-slate-900 dark:text-slate-100">
                      {rule.ruleName}
                    </p>
                    <p className="mt-1 text-slate-500 dark:text-slate-400">
                      {rule.businessLogic}
                    </p>
                  </div>
                  <Badge tone={rule.affectedRows ? "warning" : "success"}>
                    {rule.affectedRows} affected
                  </Badge>
                </div>
              ))}
            </div>
          </motion.section>
        ) : null}
      </div>
    </div>
  );
}
