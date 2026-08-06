import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Lock,
  Pencil,
  Wand2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import {
  applyIssueAutoFix,
  applyManualEdit,
  applyRuleAutoFix,
  getApiErrorMessage,
  getValidationResult,
  saveValidationResult,
} from "../services/validationService";

/** Temporary review scope: Format Validation only. */
const FORMAT_RULES = [
  {
    ruleId: "email_format",
    label: "Email Format",
    fieldName: "email",
    description:
      "Strip junk/spaces/extra @ from email. Still invalid → Change need (Edit required).",
  },
  {
    ruleId: "birthdate_validation",
    label: "Birth Date Format",
    fieldName: "birthDate",
    description:
      "Normalize birthDate to yyyy-mm-dd; blank → '1970-01-01'.",
  },
  {
    ruleId: "country_code_validation",
    label: "Country Code Format",
    fieldName: "countryCode",
    description:
      "Country code must be exactly 2 letters; uppercased on fix. Invalid → Change need.",
  },
];
const REVIEW_RULE_IDS = new Set(FORMAT_RULES.map((r) => r.ruleId));
const REVIEW_FIELDS = new Set(FORMAT_RULES.map((r) => r.fieldName));
const RULE_META = Object.fromEntries(FORMAT_RULES.map((r) => [r.ruleId, r]));
const PAGE_SIZE = 50;

function isReviewIssue(issue) {
  return (
    REVIEW_RULE_IDS.has(issue.ruleId) || REVIEW_FIELDS.has(issue.fieldName)
  );
}

function ruleLabel(ruleId, fallback = "Format rule") {
  return RULE_META[ruleId]?.label || fallback;
}

function severityBar(severity) {
  if (severity === "Error" || severity === "Critical") return "bg-rose-500";
  if (severity === "Warning") return "bg-amber-400";
  return "bg-sky-400";
}

function isChangeNeed(issue) {
  return !issue.autoFixAvailable;
}

function ActionButton({
  children,
  className = "",
  variant = "secondary",
  disabled = false,
  onClick,
}) {
  const styles =
    variant === "primary"
      ? "bg-indigo-700 text-white hover:bg-indigo-600 disabled:opacity-50"
      : variant === "ghost"
        ? "bg-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700";

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export function MembersReviewPage() {
  const navigate = useNavigate();
  const [result, setResult] = useState(() => getValidationResult());
  const [selectedRuleId, setSelectedRuleId] = useState("email_format");
  const [tab, setTab] = useState("pending");
  const [page, setPage] = useState(0);
  const [busyKey, setBusyKey] = useState(null);
  const [error, setError] = useState("");
  const [editingKey, setEditingKey] = useState(null);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    if (!result) {
      navigate("/single-upload/members/upload", { replace: true });
    }
  }, [navigate, result]);

  const issues = useMemo(
    () => (result?.affectedRows || []).filter(isReviewIssue),
    [result],
  );

  const businessRulesById = useMemo(() => {
    const map = {};
    for (const rule of result?.businessRules || []) {
      if (REVIEW_RULE_IDS.has(rule.ruleId)) {
        map[rule.ruleId] = rule;
      }
    }
    return map;
  }, [result]);

  /** Always show Format Validation rules in fixed order. */
  const navigatorRules = useMemo(
    () =>
      FORMAT_RULES.map((meta) => {
        const fromApi = businessRulesById[meta.ruleId];
        return {
          ruleId: meta.ruleId,
          ruleName: meta.label,
          category: "Format Validation",
          autoFixAvailable: fromApi?.autoFixAvailable ?? false,
          affectedRows: fromApi?.affectedRows ?? 0,
          businessLogic: fromApi?.businessLogic || meta.description,
        };
      }),
    [businessRulesById],
  );

  const selectedRule =
    navigatorRules.find((rule) => rule.ruleId === selectedRuleId) ||
    navigatorRules[0] ||
    null;

  const filteredIssues = useMemo(() => {
    let rows = issues;
    if (selectedRuleId) {
      rows = rows.filter((issue) => issue.ruleId === selectedRuleId);
    }
    if (tab === "pending") {
      rows = rows.filter((issue) => issue.status !== "Resolved");
    } else if (tab === "change-need") {
      rows = rows.filter(isChangeNeed);
    }
    return rows;
  }, [issues, selectedRuleId, tab]);

  const totalPages = Math.max(1, Math.ceil(filteredIssues.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const pageIssues = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return filteredIssues.slice(start, start + PAGE_SIZE);
  }, [filteredIssues, safePage]);

  useEffect(() => {
    setPage(0);
  }, [selectedRuleId, tab, result]);

  const pendingCount = useMemo(
    () => issues.filter((issue) => issue.status !== "Resolved").length,
    [issues],
  );
  const changeNeedCount = useMemo(
    () => issues.filter(isChangeNeed).length,
    [issues],
  );
  const canFinalize = changeNeedCount === 0;

  function ruleProgress(rule) {
    const ruleIssues = issues.filter((issue) => issue.ruleId === rule.ruleId);
    const pending = ruleIssues.length;
    const total = Math.max(rule.affectedRows || 0, pending);
    const resolved = Math.max(0, total - pending);
    return { resolved, total: total || rule.affectedRows || 0, pending };
  }

  async function refreshFromResponse(response) {
    if (response?.result) {
      saveValidationResult(response.result);
      setResult(response.result);
    }
  }

  async function handleApplyIssue(issue) {
    setBusyKey(`${issue.ruleId}:${issue.rowNumber}:apply`);
    setError("");
    try {
      const response = await applyIssueAutoFix(issue.ruleId, issue.rowNumber);
      await refreshFromResponse(response);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not apply suggested value"));
    } finally {
      setBusyKey(null);
    }
  }

  async function handleApplyRule() {
    if (!selectedRule?.autoFixAvailable) return;
    setBusyKey(`rule:${selectedRule.ruleId}`);
    setError("");
    try {
      const response = await applyRuleAutoFix(selectedRule.ruleId);
      await refreshFromResponse(response);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not apply rule fixes"));
    } finally {
      setBusyKey(null);
    }
  }

  function startEdit(issue) {
    setEditingKey(`${issue.ruleId}:${issue.rowNumber}:${issue.fieldName}`);
    setEditValue(issue.suggestedValue ?? issue.currentValue ?? "");
  }

  async function saveEdit(issue) {
    setBusyKey(`${issue.ruleId}:${issue.rowNumber}:edit`);
    setError("");
    try {
      const response = await applyManualEdit(
        issue.rowNumber,
        issue.fieldName,
        editValue,
      );
      await refreshFromResponse(response);
      setEditingKey(null);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save edit"));
    } finally {
      setBusyKey(null);
    }
  }

  if (!result) return null;

  const score = result.summary?.validationScore ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500">
            Single Upload <span className="mx-2">›</span> Members
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">
            Review Members Data
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Format Validation — apply suggested values or edit Change need rows.
          </p>
        </div>
        <Button
          variant="secondary"
          className="gap-2"
          onClick={() => navigate("/single-upload/members/upload")}
        >
          <ArrowLeft size={16} />
          Back
        </Button>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)_240px]">
        <aside className="rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Rule Navigator
          </p>
          <p className="mt-2 px-2 text-[11px] uppercase tracking-wide text-slate-400">
            Format Validation
          </p>
          <ul className="mt-1 space-y-1">
            {navigatorRules.map((rule) => {
              const progress = ruleProgress(rule);
              const active =
                (selectedRule?.ruleId || selectedRuleId) === rule.ruleId;
              const done = progress.pending === 0 && progress.total > 0;
              return (
                <li key={rule.ruleId}>
                  <button
                    type="button"
                    onClick={() => setSelectedRuleId(rule.ruleId)}
                    className={`flex w-full items-start justify-between gap-2 rounded-xl px-3 py-2 text-left text-sm ${
                      active
                        ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                        : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate">{rule.ruleName}</span>
                      <span className="text-[11px] text-slate-400">
                        {progress.resolved}/{progress.total || rule.affectedRows}{" "}
                        resolved
                      </span>
                    </span>
                    {done ? (
                      <CheckCircle2
                        size={16}
                        className="mt-0.5 shrink-0 text-emerald-500"
                      />
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="min-w-0 rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
            {[
              { id: "all", label: `All Issues (${issues.length})` },
              { id: "pending", label: `Pending Review (${pendingCount})` },
              {
                id: "change-need",
                label: `Change Need (${changeNeedCount})`,
              },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                  tab === item.id
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                    : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                {item.label}
              </button>
            ))}
            {selectedRule?.autoFixAvailable ? (
              <ActionButton
                className="ml-auto"
                disabled={busyKey === `rule:${selectedRule.ruleId}`}
                onClick={handleApplyRule}
              >
                <Wand2 size={14} />
                Apply all suggested
              </ActionButton>
            ) : null}
          </div>

          {selectedRule &&
          selectedRule.affectedRows > 0 &&
          !selectedRule.autoFixAvailable ? (
            <div className="mx-4 mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              Auto Apply: Disabled for some{" "}
              {ruleLabel(selectedRule.ruleId).toLowerCase()} rows — Change need
              requires Edit.
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-950/50 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-semibold">Row</th>
                  <th className="px-4 py-3 font-semibold">Affected Field</th>
                  <th className="px-4 py-3 font-semibold">Current Value</th>
                  <th className="px-4 py-3 font-semibold">Suggested Value</th>
                  <th className="px-4 py-3 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {pageIssues.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-10 text-center text-slate-500"
                    >
                      No issues for this rule in the current view.
                    </td>
                  </tr>
                ) : (
                  pageIssues.map((issue) => {
                    const rowKey = `${issue.ruleId}:${issue.rowNumber}:${issue.fieldName}`;
                    const isEditing = editingKey === rowKey;
                    const applyBusy =
                      busyKey === `${issue.ruleId}:${issue.rowNumber}:apply`;
                    const editBusy =
                      busyKey === `${issue.ruleId}:${issue.rowNumber}:edit`;
                    return (
                      <tr key={rowKey} className="align-top">
                        <td className="px-4 py-3">
                          <div className="font-semibold text-slate-900 dark:text-white">
                            #{issue.rowNumber}
                          </div>
                          <div className="text-xs text-slate-500">
                            {issue.memberId
                              ? `ID: ${issue.memberId}`
                              : "ID: —"}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-start gap-2">
                            <span
                              className={`mt-0.5 h-8 w-1 shrink-0 rounded-full ${severityBar(issue.severity)}`}
                            />
                            <div>
                              <div className="font-medium text-slate-800 dark:text-slate-100">
                                {issue.fieldName}
                              </div>
                              <div className="text-xs text-slate-500">
                                {ruleLabel(issue.ruleId, issue.ruleName)}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="max-w-xs break-all text-sm text-slate-700 dark:text-slate-200">
                            {issue.currentValue ?? (
                              <span className="text-slate-400">(blank)</span>
                            )}
                          </div>
                          {isChangeNeed(issue) && !isEditing ? (
                            <div className="mt-1 flex items-center gap-1 text-[11px] text-rose-600 dark:text-rose-400">
                              <AlertTriangle size={12} />
                              Change need
                            </div>
                          ) : null}
                        </td>
                        <td className="px-4 py-3">
                          {isEditing ? (
                            <input
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              autoFocus
                              className="w-full min-w-44 rounded-lg border border-indigo-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 shadow-sm outline-none ring-2 ring-indigo-100 focus:border-indigo-400 dark:border-indigo-700 dark:bg-slate-950 dark:text-white dark:ring-indigo-950"
                            />
                          ) : issue.suggestedValue != null ? (
                            <div className="max-w-xs break-all text-sm font-medium text-slate-900 dark:text-slate-100">
                              {issue.suggestedValue}
                            </div>
                          ) : (
                            <span className="text-sm text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {isEditing ? (
                              <>
                                <ActionButton
                                  variant="primary"
                                  disabled={editBusy}
                                  onClick={() => saveEdit(issue)}
                                >
                                  Save
                                </ActionButton>
                                <ActionButton
                                  variant="ghost"
                                  onClick={() => setEditingKey(null)}
                                >
                                  Cancel
                                </ActionButton>
                              </>
                            ) : (
                              <>
                                <ActionButton onClick={() => startEdit(issue)}>
                                  <Pencil size={12} />
                                  Edit
                                </ActionButton>
                                {issue.autoFixAvailable ? (
                                  <ActionButton
                                    variant="primary"
                                    disabled={applyBusy}
                                    onClick={() => handleApplyIssue(issue)}
                                  >
                                    <Wand2 size={12} />
                                    Accept
                                  </ActionButton>
                                ) : null}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {filteredIssues.length > PAGE_SIZE ? (
            <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-xs text-slate-500 dark:border-slate-800">
              <span>
                Showing {safePage * PAGE_SIZE + 1}–
                {Math.min((safePage + 1) * PAGE_SIZE, filteredIssues.length)} of{" "}
                {filteredIssues.length}
              </span>
              <div className="flex items-center gap-2">
                <ActionButton
                  disabled={safePage <= 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft size={14} />
                  Prev
                </ActionButton>
                <span>
                  Page {safePage + 1} / {totalPages}
                </span>
                <ActionButton
                  disabled={safePage >= totalPages - 1}
                  onClick={() =>
                    setPage((p) => Math.min(totalPages - 1, p + 1))
                  }
                >
                  Next
                  <ChevronRight size={14} />
                </ActionButton>
              </div>
            </div>
          ) : null}
        </section>

        <aside className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-col items-center rounded-xl bg-slate-50 px-4 py-5 dark:bg-slate-950/50">
            <div className="flex h-24 w-24 items-center justify-center rounded-full border-4 border-emerald-400 text-2xl font-semibold text-slate-900 dark:text-white">
              {Math.round(score)}%
            </div>
            <p className="mt-2 text-center text-xs text-slate-500">
              Validation score
            </p>
          </div>

          <div className="mt-4 space-y-3 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Rule Diagnostics
            </p>
            <div>
              <p className="text-xs text-slate-500">Business Rule</p>
              <p className="font-medium text-slate-900 dark:text-white">
                {selectedRule
                  ? ruleLabel(selectedRule.ruleId, selectedRule.ruleName)
                  : "—"}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg bg-slate-50 p-2 dark:bg-slate-950/50">
                <p className="text-slate-500">Affected</p>
                <p className="mt-0.5 font-semibold text-slate-900 dark:text-white">
                  {selectedRule
                    ? issues.filter((i) => i.ruleId === selectedRule.ruleId)
                        .length
                    : 0}{" "}
                  issues
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-2 dark:bg-slate-950/50">
                <p className="text-slate-500">Auto Fix</p>
                <p
                  className={`mt-0.5 font-semibold ${
                    selectedRule?.autoFixAvailable
                      ? "text-emerald-600"
                      : selectedRule?.affectedRows
                        ? "text-rose-600"
                        : "text-slate-500"
                  }`}
                >
                  {selectedRule?.autoFixAvailable
                    ? "Yes"
                    : selectedRule?.affectedRows
                      ? "No / Mixed"
                      : "—"}
                </p>
              </div>
            </div>
            <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
              {selectedRule?.businessLogic ||
                RULE_META[selectedRuleId]?.description ||
                "Select a format rule to see diagnostics."}
            </p>
            {changeNeedCount > 0 ? (
              <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300">
                <Lock size={14} className="mt-0.5 shrink-0" />
                {changeNeedCount} Change need issue
                {changeNeedCount === 1 ? "" : "s"} block finalizing.
              </div>
            ) : (
              <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
                <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
                No Change need rows left. You can finalize.
              </div>
            )}
          </div>
        </aside>
      </div>

      <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
        <p className="text-xs text-slate-500">
          Showing {PAGE_SIZE} rows per page for speed. Re-upload after restarting
          the backend to pick up format validation rules.
        </p>
        <Button
          className="gap-2 bg-indigo-700 hover:bg-indigo-600 dark:bg-indigo-600 dark:text-white"
          disabled={!canFinalize}
          onClick={() => navigate("/single-upload/members/results")}
        >
          {canFinalize ? (
            "Finalize Review & Continue"
          ) : (
            <>
              <Lock size={14} />
              Fix Change Need to Continue
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
