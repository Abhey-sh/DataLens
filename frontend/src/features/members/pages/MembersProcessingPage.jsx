import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  ClipboardCheck,
  Clock3,
  CopyCheck,
  Database,
  DatabaseZap,
  FileSpreadsheet,
  Gauge,
  Languages,
  LoaderCircle,
  MailCheck,
  Scale,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Terminal,
  UploadCloud,
  XCircle,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import { Stepper } from "../../../components/ui/Stepper";
import {
  getApiErrorMessage,
  getMembersValidationProgress,
  startMembersValidation,
} from "../services/validationService";

const pipelineSteps = [
  {
    id: "upload",
    title: "Upload source dataset",
    description: "Securely transferring the members CSV",
    icon: UploadCloud,
    gradient: "from-cyan-400 to-blue-500",
  },
  {
    id: "parse",
    title: "Read CSV structure",
    description: "Inspecting columns, rows, and file structure",
    icon: FileSpreadsheet,
    gradient: "from-blue-500 to-indigo-500",
  },
  {
    id: "encoding",
    title: "Detect encoding & locale",
    description: "Normalizing text and regional data formats",
    icon: Languages,
    gradient: "from-fuchsia-500 to-violet-500",
  },
  {
    id: "validate",
    title: "Validate member fields",
    description: "Checking email, schema, defaults, and allowed values",
    icon: MailCheck,
    gradient: "from-violet-600 to-indigo-500",
  },
  {
    id: "rules",
    title: "Apply business rules",
    description: "Evaluating member-specific import requirements",
    icon: Scale,
    gradient: "from-orange-400 to-amber-500",
  },
  {
    id: "prepare",
    title: "Prepare review dataset",
    description: "Organizing issues and migration-ready records",
    icon: DatabaseZap,
    gradient: "from-emerald-500 to-green-400",
  },
  {
    id: "complete",
    title: "Validation complete",
    description: "Results are ready for review and correction",
    icon: BadgeCheck,
    gradient: "from-emerald-500 to-cyan-400",
  },
];

const cardEntrance = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0 },
};

function formatDuration(seconds) {
  if (seconds == null) return "Calculating…";
  if (seconds < 1) return "<1s";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return minutes
    ? `${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`
    : `${remainingSeconds}s`;
}

function statusLabel(status) {
  return {
    completed: "Completed",
    running: "Current",
    failed: "Failed",
    queued: "Pending",
    "not-run": "Not run",
  }[status];
}

export function MembersProcessingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [completion, setCompletion] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const terminalRef = useRef(null);

  useEffect(() => {
    const file = location.state?.file;
    if (!file) {
      navigate("/single-upload/members/upload", { replace: true });
      return undefined;
    }

    let cancelled = false;
    const controller = new AbortController();
    let pollTimer;

    const pollProgress = async (validationId) => {
      try {
        const latest = await getMembersValidationProgress(validationId, {
          signal: controller.signal,
        });
        if (cancelled) return;
        setProgress(latest);

        if (latest.status === "completed" && latest.result) {
          setCompletion(100);
          setResult(latest.result);
          return;
        }
        if (latest.status === "failed") {
          setError(latest.error || "Validation failed");
          return;
        }

        const validationPercent = latest.totalSteps
          ? Math.round((latest.completedSteps / latest.totalSteps) * 65)
          : 0;
        setCompletion(25 + validationPercent);
        pollTimer = window.setTimeout(
          () => pollProgress(validationId),
          500,
        );
      } catch (requestError) {
        if (!cancelled && requestError.code !== "ERR_CANCELED") {
          setError(getApiErrorMessage(requestError));
        }
      }
    };

    startMembersValidation(file, {
      signal: controller.signal,
      onUploadProgress: (event) => {
        if (!cancelled && event.total) {
          setCompletion(
            Math.min(20, Math.round((event.loaded / event.total) * 20)),
          );
        }
      },
    })
      .then((job) => {
        if (cancelled) return;
        setCompletion(25);
        pollProgress(job.validationId);
      })
      .catch((requestError) => {
        if (!cancelled && requestError.code !== "ERR_CANCELED") {
          setError(getApiErrorMessage(requestError));
        }
      });

    return () => {
      cancelled = true;
      window.clearTimeout(pollTimer);
      controller.abort();
    };
  }, [attempt, location.state, navigate]);

  const progressLabel = useMemo(() => {
    if (error) return "Validation failed";
    if (result) return "Ready for review";
    if (progress?.currentStep) return progress.currentStep;
    if (completion < 20) return "Uploading CSV";
    return "Reading CSV file";
  }, [completion, error, progress, result]);

  const getStepStatus = (step) => {
    if (step.id === "upload") {
      return completion >= 20 || progress || result || error
        ? "completed"
        : "running";
    }
    if (step.id === "parse") {
      if (error && !progress) return "failed";
      if (progress || result) return "completed";
      return completion >= 20 ? "running" : "queued";
    }
    if (step.id === "encoding") {
      if (error && !progress) return "not-run";
      if (progress || result) return "completed";
      return "queued";
    }
    if (step.id === "validate") {
      if (error) return "failed";
      if (result || progress?.status === "completed") return "completed";
      const midpoint = Math.ceil((progress?.totalSteps ?? 0) / 2);
      if (
        progress?.totalSteps &&
        progress?.stage === "validating" &&
        progress.completedSteps >= midpoint
      ) {
        return "completed";
      }
      return progress?.stage === "validating" ? "running" : "queued";
    }
    if (step.id === "rules") {
      if (error) return "failed";
      if (result || progress?.status === "completed") return "completed";
      const midpoint = Math.ceil((progress?.totalSteps ?? 0) / 2);
      if (
        progress?.totalSteps &&
        progress?.stage === "validating" &&
        progress.completedSteps >= midpoint
      ) {
        return "running";
      }
      return "queued";
    }
    if (step.id === "prepare") {
      if (error) return "not-run";
      if (result) return "completed";
      return progress?.stage === "preparing" ? "running" : "queued";
    }
    if (step.id === "complete") {
      if (result) return "completed";
      return error ? "not-run" : "queued";
    }
    return "queued";
  };

  const completedCheckDuration = useMemo(
    () =>
      (progress?.checks ?? []).reduce(
        (total, check) => total + (check.durationMs ?? 0),
        0,
      ) / 1000,
    [progress],
  );

  const validationSpeed =
    progress?.elapsedTime > 0
      ? Math.round(progress.recordsScanned / progress.elapsedTime)
      : null;

  const engineLogs = useMemo(() => {
    if (error) {
      return [{ level: "ERROR", message: error }];
    }
    const logs = (progress?.checks ?? [])
      .filter((check) => check.status !== "pending")
      .map((check) => ({
        level:
          check.status === "failed"
            ? "ERROR"
            : check.status === "running"
              ? "INFO"
              : check.issuesFound
                ? "WARNING"
                : "SUCCESS",
        message:
          check.status === "running"
            ? `${check.name} is running`
            : `${check.name}: ${check.issuesFound} issue${check.issuesFound === 1 ? "" : "s"}`,
      }));
    if (!logs.length) {
      logs.push({
        level: "INFO",
        message:
          completion < 20
            ? "Uploading members dataset"
            : "Initializing validation engine",
      });
    }
    if (result) {
      logs.push({
        level: "SUCCESS",
        message: `${result.summary.totalRecords.toLocaleString()} records validated`,
      });
    }
    return logs.slice(-8);
  }, [completion, error, progress, result]);

  useEffect(() => {
    terminalRef.current?.scrollTo({
      top: terminalRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [engineLogs]);

  const retryValidation = () => {
    setCompletion(0);
    setResult(null);
    setError("");
    setProgress(null);
    setAttempt((current) => current + 1);
  };

  const rowsPercent = progress?.totalRecords
    ? Math.min(100, (progress.recordsScanned / progress.totalRecords) * 100)
    : result
      ? 100
      : 0;
  const checksPercent = progress?.totalSteps
    ? Math.min(100, (progress.completedSteps / progress.totalSteps) * 100)
    : 0;
  const currentCheck = progress?.checks?.find(
    (check) => check.status === "running",
  );
  const currentRule = result
    ? "Review ready"
    : currentCheck?.name ?? progressLabel;
  const passedChecks =
    progress?.checks?.filter(
      (check) => check.status === "completed" && check.issuesFound === 0,
    ).length ?? 0;

  const metrics = [
    {
      label: "Elapsed time",
      value: progress ? formatDuration(progress.elapsedTime) : "—",
      description: "Total processing time",
      icon: Clock3,
      gradient: "from-blue-500 to-cyan-400",
      tint: "from-blue-50 to-cyan-50/40 dark:from-blue-950/35 dark:to-cyan-950/10",
      percent: progress?.elapsedTime ? 100 : 0,
    },
    {
      label: "Rows processed",
      value: progress
        ? progress.recordsScanned.toLocaleString()
        : result
          ? result.summary.totalRecords.toLocaleString()
          : "—",
      description: progress?.totalRecords
        ? `of ${progress.totalRecords.toLocaleString()} rows`
        : "Waiting for dataset",
      icon: Database,
      gradient: "from-violet-600 to-indigo-500",
      tint: "from-violet-50 to-indigo-50/40 dark:from-violet-950/35 dark:to-indigo-950/10",
      percent: rowsPercent,
    },
    {
      label: "Validation speed",
      value: validationSpeed == null ? "—" : `${validationSpeed}/s`,
      description: "Rows checked per second",
      icon: Zap,
      gradient: "from-orange-400 to-amber-500",
      tint: "from-orange-50 to-amber-50/40 dark:from-orange-950/35 dark:to-amber-950/10",
      percent: validationSpeed == null ? 0 : Math.min(100, validationSpeed),
    },
    {
      label: "Checks completed",
      value: progress?.totalSteps
        ? `${progress.completedSteps}/${progress.totalSteps}`
        : "—",
      description: "Business and field checks",
      icon: ClipboardCheck,
      gradient: "from-emerald-500 to-green-400",
      tint: "from-emerald-50 to-green-50/40 dark:from-emerald-950/35 dark:to-green-950/10",
      percent: checksPercent,
    },
    {
      label: "Confidence",
      value:
        progress?.validationScore != null
          ? `${progress.validationScore}%`
          : "—",
      description: "Current validation score",
      icon: ShieldCheck,
      gradient: "from-cyan-400 to-blue-500",
      tint: "from-cyan-50 to-blue-50/40 dark:from-cyan-950/35 dark:to-blue-950/10",
      percent: progress?.validationScore ?? 0,
    },
    {
      label: "Current rule",
      value: currentRule,
      description: result ? "Validation complete" : "Actively evaluating",
      icon: ScanSearch,
      gradient: "from-pink-500 to-purple-500",
      tint: "from-pink-50 to-purple-50/40 dark:from-pink-950/35 dark:to-purple-950/10",
      percent: checksPercent,
      compact: true,
    },
  ];

  return (
    <div className="relative isolate -mx-4 -my-6 min-h-screen overflow-hidden px-4 py-6 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_8%_8%,rgba(139,92,246,0.14),transparent_28%),radial-gradient(circle_at_92%_4%,rgba(59,130,246,0.13),transparent_27%),linear-gradient(to_bottom,rgba(248,250,252,0.72),rgba(255,255,255,0.98))] dark:bg-[radial-gradient(circle_at_8%_8%,rgba(124,58,237,0.18),transparent_28%),radial-gradient(circle_at_92%_4%,rgba(37,99,235,0.16),transparent_27%),linear-gradient(to_bottom,#090d18,#0f172a)]" />
      <div className="mx-auto max-w-[1500px] space-y-5">
        <motion.header
          initial="hidden"
          animate="visible"
          variants={cardEntrance}
          className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
        >
          <div>
            <button
              type="button"
              onClick={() => navigate("/single-upload/members/upload")}
              className="mb-2 inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:-translate-x-0.5 hover:text-violet-700 dark:text-slate-400 dark:hover:text-violet-300"
            >
              <ArrowLeft size={16} />
              Back to upload
            </button>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-violet-600 dark:text-violet-400">
              DataLens validation engine
            </p>
            <h1 className="mt-1.5 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">
              Members Dataset Validation
            </h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              Preparing migration-ready data with live quality checks.
            </p>
          </div>
          <Stepper currentStep={2} />
        </motion.header>

        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.85fr)_minmax(340px,1fr)] xl:items-stretch">
          <motion.main
            initial="hidden"
            animate="visible"
            variants={cardEntrance}
            transition={{ delay: 0.08 }}
            className="h-full overflow-hidden rounded-[20px] border border-white/70 bg-white/80 shadow-[0_24px_80px_-32px_rgba(76,29,149,0.35)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/70"
          >
            <div className="border-b border-slate-200/70 p-5 sm:p-6 dark:border-slate-800">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    Overall progress
                  </p>
                  <h2 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">
                    {progressLabel}
                  </h2>
                </div>
                <motion.div
                  animate={
                    result
                      ? { scale: 1 }
                      : { boxShadow: ["0 0 0 rgba(124,58,237,0)", "0 0 24px rgba(124,58,237,.35)", "0 0 0 rgba(124,58,237,0)"] }
                  }
                  transition={{ repeat: result ? 0 : Infinity, duration: 2 }}
                  className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-indigo-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-violet-500/20"
                >
                  {result ? (
                    <BadgeCheck size={15} />
                  ) : (
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-70" />
                      <span className="relative h-2 w-2 rounded-full bg-white" />
                    </span>
                  )}
                  {result ? "Validation Complete" : "Live Validation"}
                </motion.div>
              </div>

              <div className="mt-5 flex items-end justify-between">
                <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
                  {progress?.completedSteps ?? 0} of {progress?.totalSteps ?? "—"} checks
                </span>
                <motion.span
                  key={completion}
                  initial={{ opacity: 0.4, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-3xl font-bold tracking-tight text-violet-700 dark:text-violet-300"
                >
                  {completion}%
                </motion.span>
              </div>
              <div className="relative mt-3 h-3 overflow-hidden rounded-full bg-slate-100 shadow-inner dark:bg-slate-800">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${completion}%` }}
                  transition={{ type: "spring", stiffness: 80, damping: 18 }}
                  className="relative h-full overflow-hidden rounded-full bg-gradient-to-r from-violet-600 via-indigo-500 to-cyan-400"
                >
                  {!result ? (
                    <motion.span
                      animate={{ x: ["-100%", "300%"] }}
                      transition={{ repeat: Infinity, duration: 1.6, ease: "linear" }}
                      className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/60 to-transparent"
                    />
                  ) : null}
                </motion.div>
              </div>
            </div>

            <div className="p-5 sm:p-6">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    Validation pipeline
                  </p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Every stage updates from the active backend job.
                  </p>
                </div>
                {completedCheckDuration > 0 ? (
                  <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                    Checks: {formatDuration(completedCheckDuration)}
                  </span>
                ) : null}
              </div>

              <div className="relative">
                <div className="absolute bottom-8 left-6 top-8 w-px bg-gradient-to-b from-cyan-300 via-violet-300 to-emerald-300 dark:from-cyan-900 dark:via-violet-900 dark:to-emerald-900" />
                <div className="space-y-2">
                  {pipelineSteps.map((step, index) => {
                    const status = getStepStatus(step);
                    const Icon = step.icon;
                    const duration =
                      step.id === "validate" && completedCheckDuration > 0
                        ? formatDuration(completedCheckDuration)
                        : step.id === "complete" && result
                          ? formatDuration(result.summary.executionTime)
                          : null;
                    return (
                      <motion.div
                        key={step.id}
                        initial={{ opacity: 0, x: -12 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.12 + index * 0.07 }}
                        whileHover={{ y: -2, scale: 1.005 }}
                        className={`relative flex items-center gap-3 rounded-2xl border p-3 transition-shadow hover:shadow-lg ${
                          status === "running"
                            ? "border-violet-300 bg-violet-50/80 shadow-violet-200/40 dark:border-violet-700 dark:bg-violet-950/30"
                            : status === "failed"
                              ? "border-rose-200 bg-rose-50/80 dark:border-rose-900 dark:bg-rose-950/20"
                              : "border-slate-200/80 bg-white/80 dark:border-slate-800 dark:bg-slate-900/70"
                        }`}
                      >
                        <div
                          className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                            status === "queued" || status === "not-run"
                              ? "border-2 border-slate-200 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900"
                              : status === "failed"
                                ? "bg-gradient-to-br from-rose-500 to-red-500 text-white shadow-lg shadow-rose-500/20"
                                : `bg-gradient-to-br ${step.gradient} text-white shadow-lg`
                          }`}
                        >
                          {status === "running" ? (
                            <LoaderCircle size={18} className="animate-spin" />
                          ) : status === "failed" ? (
                            <XCircle size={18} />
                          ) : status === "completed" ? (
                            <Icon size={18} />
                          ) : (
                            <Icon size={17} />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                            {step.title}
                          </h3>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            {step.description}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {duration ? (
                            <span className="text-xs tabular-nums text-slate-400">
                              {duration}
                            </span>
                          ) : null}
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            status === "completed"
                              ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                              : status === "running"
                                ? "bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300"
                                : status === "failed"
                                  ? "bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
                                  : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                            }`}
                          >
                            {statusLabel(status)}
                          </span>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </div>

              <AnimatePresence mode="wait">
                {error ? (
                  <motion.div
                    key="error"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-7 rounded-2xl border border-rose-200 bg-gradient-to-r from-rose-50 to-red-50 p-5 dark:border-rose-900/50 dark:from-rose-950/30 dark:to-red-950/20"
                  >
                    <div className="flex items-start gap-3">
                      <XCircle className="mt-0.5 text-rose-600" size={21} />
                      <div>
                        <p className="font-semibold text-rose-900 dark:text-rose-100">
                          Validation stopped
                        </p>
                        <p className="mt-1 text-sm text-rose-700 dark:text-rose-300">
                          {error}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button onClick={retryValidation}>Retry validation</Button>
                      <Button
                        variant="secondary"
                        onClick={() => navigate("/single-upload/members/upload")}
                      >
                        Choose another file
                      </Button>
                    </div>
                  </motion.div>
                ) : result ? (
                  <motion.div
                    key="ready"
                    initial={{ opacity: 0, y: 12, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    className="relative mt-5 overflow-hidden rounded-2xl bg-gradient-to-br from-violet-600 via-indigo-600 to-blue-500 p-5 text-white shadow-xl shadow-indigo-500/20"
                  >
                    <div className="absolute -right-10 -top-10 h-36 w-36 rounded-full bg-cyan-300/20 blur-2xl" />
                    <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex gap-4">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
                          <Sparkles size={22} />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold">Validation Ready</h3>
                          <p className="mt-1 text-sm text-indigo-100">
                            Review detected issues before finalizing the import.
                          </p>
                        </div>
                      </div>
                      <motion.button
                        whileHover={{ y: -2, scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => navigate("/single-upload/members/review")}
                        className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-indigo-700 shadow-lg shadow-indigo-950/20"
                      >
                        Continue to Review
                        <ArrowRight size={16} />
                      </motion.button>
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          </motion.main>

          <motion.aside
            initial="hidden"
            animate="visible"
            variants={cardEntrance}
            transition={{ delay: 0.16 }}
            className="flex flex-col gap-4 xl:sticky xl:top-5 xl:h-full"
          >
            <section className="rounded-[20px] border border-white/70 bg-white/80 p-4 shadow-[0_20px_60px_-30px_rgba(37,99,235,0.35)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/70">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    Live metrics
                  </p>
                  <h2 className="mt-1 text-xl font-bold text-slate-950 dark:text-white">
                    Validation pulse
                  </h2>
                </div>
                <motion.div
                  animate={{ scale: [1, 1.08, 1] }}
                  transition={{ repeat: Infinity, duration: 2 }}
                  className="rounded-xl bg-gradient-to-br from-cyan-400 to-blue-500 p-2.5 text-white shadow-lg shadow-cyan-500/20"
                >
                  <Activity size={19} />
                </motion.div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2.5">
                {metrics.map((metric, index) => {
                  const Icon = metric.icon;
                  return (
                    <motion.div
                      key={metric.label}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2 + index * 0.05 }}
                      whileHover={{ y: -3 }}
                      className={`group rounded-2xl border border-slate-200/80 bg-gradient-to-br p-3 shadow-sm transition-shadow hover:shadow-lg dark:border-slate-800 ${metric.tint}`}
                    >
                      <div
                        className={`flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br ${metric.gradient} text-white shadow-md transition-transform group-hover:scale-105`}
                      >
                        <Icon size={17} />
                      </div>
                      <motion.p
                        key={metric.value}
                        initial={{ opacity: 0.4, y: 3 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`${metric.compact ? "mt-2 truncate text-sm" : "mt-2 text-xl"} font-bold tracking-tight text-slate-950 dark:text-white`}
                      >
                        {metric.value}
                      </motion.p>
                      <p className="mt-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
                        {metric.label}
                      </p>
                      <p className="mt-1 truncate text-[11px] text-slate-400">
                        {metric.description}
                      </p>
                      <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/80 shadow-inner dark:bg-slate-800">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${metric.percent}%` }}
                          className={`h-full rounded-full bg-gradient-to-r ${metric.gradient}`}
                        />
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </section>

            <section className="overflow-hidden rounded-[20px] border border-violet-200/70 bg-gradient-to-br from-violet-50 via-indigo-50 to-blue-50 p-4 shadow-[0_18px_55px_-30px_rgba(79,70,229,0.45)] dark:border-violet-900/60 dark:from-violet-950/35 dark:via-indigo-950/30 dark:to-blue-950/25">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-600 dark:text-violet-400">
                    Validation statistics
                  </p>
                  <h2 className="mt-1 font-bold text-slate-950 dark:text-white">
                    Active workload
                  </h2>
                </div>
                <div className="rounded-full bg-gradient-to-br from-violet-600 to-indigo-500 p-2.5 text-white shadow-lg shadow-violet-500/20">
                  <Gauge size={18} />
                </div>
              </div>
              <div className="mt-4 space-y-3">
                <StatisticBar
                  label="Record coverage"
                  value={`${Math.round(rowsPercent)}%`}
                  percent={rowsPercent}
                  gradient="from-violet-600 to-indigo-500"
                />
                <StatisticBar
                  label="Check completion"
                  value={`${progress?.completedSteps ?? 0}/${progress?.totalSteps ?? "—"}`}
                  percent={checksPercent}
                  gradient="from-emerald-500 to-green-400"
                />
                <div className="grid grid-cols-3 gap-2 border-t border-violet-200/60 pt-3 dark:border-violet-900/50">
                  <CompactStat
                    label="Passed"
                    value={passedChecks.toLocaleString()}
                    tone="text-emerald-600 dark:text-emerald-400"
                  />
                  <CompactStat
                    label="Issues"
                    value={(progress?.potentialIssues ?? 0).toLocaleString()}
                    tone="text-amber-600 dark:text-amber-400"
                  />
                  <CompactStat
                    label="Remaining"
                    value={
                      result
                        ? "Done"
                        : formatDuration(progress?.estimatedRemaining)
                    }
                    tone="text-indigo-600 dark:text-indigo-400"
                  />
                </div>
              </div>
            </section>

            <section className="flex min-h-52 flex-col overflow-hidden rounded-[20px] border border-slate-700/70 bg-[#0b1020] shadow-[0_24px_70px_-30px_rgba(15,23,42,0.9)] xl:min-h-0 xl:flex-1">
              <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  </div>
                  <Terminal size={15} className="text-violet-400" />
                  <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                    Validation engine
                  </span>
                </div>
                <CopyCheck size={15} className="text-slate-500" />
              </div>
              <div
                ref={terminalRef}
                className="validation-terminal-scrollbar h-52 overflow-y-auto p-4 font-mono text-xs xl:h-auto xl:min-h-0 xl:flex-1"
              >
                <AnimatePresence initial={false}>
                  {engineLogs.map((log, index) => (
                    <motion.div
                      key={`${log.level}-${log.message}`}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.04 }}
                      className="mb-3 flex items-start gap-3"
                    >
                      <span
                        className={`w-16 shrink-0 font-semibold ${
                          log.level === "SUCCESS"
                            ? "text-emerald-400"
                            : log.level === "WARNING"
                              ? "text-amber-400"
                              : log.level === "ERROR"
                                ? "text-rose-400"
                                : "text-cyan-400"
                        }`}
                      >
                        {log.level}
                      </span>
                      <span className="leading-relaxed text-slate-300">
                        {log.message}
                      </span>
                    </motion.div>
                  ))}
                </AnimatePresence>
                {!result && !error ? (
                  <span className="inline-block h-4 w-2 animate-pulse bg-violet-400" />
                ) : null}
              </div>
            </section>
          </motion.aside>
        </div>
      </div>
    </div>
  );
}

function StatisticBar({ label, value, percent, gradient }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600 dark:text-slate-300">
          {label}
        </span>
        <span className="font-bold tabular-nums text-slate-900 dark:text-white">
          {value}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/80 shadow-inner dark:bg-slate-800">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.45 }}
          className={`h-full rounded-full bg-gradient-to-r ${gradient}`}
        />
      </div>
    </div>
  );
}

function CompactStat({ label, value, tone }) {
  return (
    <motion.div
      whileHover={{ y: -2 }}
      className="rounded-xl border border-white/80 bg-white/65 p-2 text-center shadow-sm dark:border-white/10 dark:bg-slate-900/55"
    >
      <p className={`truncate text-sm font-bold tabular-nums ${tone}`}>{value}</p>
      <p className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-400">
        {label}
      </p>
    </motion.div>
  );
}
