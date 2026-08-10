import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Lock,
  Pencil,
  Wand2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CloudUpload,
  Database,
  Filter,
  Layers3,
  LoaderCircle,
  Pencil,
  Sparkles,
  Wand2,
  WandSparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import {
  applyIssueAutoFix,
  applyManualEdit,
  applyRuleAutoFix,
  bulkFillBlankValues,
  getApiErrorMessage,
  getValidationResult,
  saveValidationResult,
} from "../services/validationService";

const DETAIL_RULES = {
  email_format: { fieldName: "email", label: "Email Format" },
  first_name_default: { fieldName: "firstName", label: "First Name Cleanup" },
  last_name_default: { fieldName: "lastName", label: "Last Name Cleanup" },
  gender_validation: { fieldName: "gender", label: "Gender Validation" },
  lead_status_validation: {
    fieldName: "leadStatus",
    label: "Lead Status Validation",
  },
  joined_date_validation: {
    fieldName: "joinedDate",
    label: "Joined Date Validation",
  },
};

const BULK_FILL_PROTECTED_FIELDS = new Set([
  "userForeignId",
  "email",
  "accessBarcode",
]);

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

function humanize(value) {
  return value
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isBlank(value) {
  return value == null || String(value).trim() === "";
}

function isBlankIssue(issue) {
  return (
    issue?.issueType === "blank" ||
    (issue?.rowNumber > 0 && isBlank(issue?.currentValue))
  );
}

function isChangeNeed(issue) {
  return !issue.autoFixAvailable;
}

function getDetailRuleMeta(ruleId, fieldName) {
  const meta = DETAIL_RULES[ruleId];
  if (!meta || meta.fieldName !== fieldName) return null;
  return meta;
}

function severityBar(severity) {
  if (severity === "Error" || severity === "Critical") return "bg-rose-500";
  if (severity === "Warning") return "bg-amber-400";
  return "bg-sky-400";
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
      : variant === "success"
        ? "bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
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

  const [initialResult] = useState(() => getValidationResult());
  const [result, setResult] = useState(initialResult);
  const [selectedRuleKey, setSelectedRuleKey] = useState("all");
  const [issueTab, setIssueTab] = useState("all");
  const [collapsedCategories, setCollapsedCategories] = useState(new Set());
  const [showBulkFill, setShowBulkFill] = useState(false);
  const [bulkField, setBulkField] = useState("");
  const [bulkValue, setBulkValue] = useState("");
  const [isApplyingBulk, setIsApplyingBulk] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState(null);
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
  useEffect(() => {
    setEditingKey(null);
  }, [selectedRuleKey]);

  const baselineIssues = useMemo(
    () => initialResult?.affectedRows ?? [],
    [initialResult],
  );
  const currentIssues = useMemo(
    () => result?.affectedRows ?? [],
    [result],
  );

  const ruleCatalog = useMemo(() => {
    const catalog = new Map();
    for (const rule of [
      ...(initialResult?.businessRules ?? []),
      ...(result?.businessRules ?? []),
    ]) {
      catalog.set(rule.ruleId, rule);
    }
    return catalog;
  }, [initialResult, result]);

  const navigatorGroups = useMemo(() => {
    const baselineItems = new Map();
    for (const issue of baselineIssues) {
      const issueType = isBlankIssue(issue) ? "blank" : "issue";
      const key = `${issue.ruleId}:${issue.fieldName}:${issueType}`;
      const item = baselineItems.get(key) ?? {
        key,
        ruleId: issue.ruleId,
        fieldName: issue.fieldName,
        issueType,
        rule: ruleCatalog.get(issue.ruleId),
        baselineRows: new Set(),
      };
      if (issue.rowNumber > 0) item.baselineRows.add(issue.rowNumber);
      baselineItems.set(key, item);
    }

    for (const issue of currentIssues) {
      const issueType = isBlankIssue(issue) ? "blank" : "issue";
      const key = `${issue.ruleId}:${issue.fieldName}:${issueType}`;
      if (!baselineItems.has(key)) {
        baselineItems.set(key, {
          key,
          ruleId: issue.ruleId,
          fieldName: issue.fieldName,
          issueType,
          rule: ruleCatalog.get(issue.ruleId),
          baselineRows: new Set(),
        });
      }
    }

    const groups = new Map();
    for (const item of baselineItems.values()) {
      const unresolvedRows = new Set(
        currentIssues
          .filter(
            (issue) =>
              issue.ruleId === item.ruleId &&
              issue.fieldName === item.fieldName &&
              (isBlankIssue(issue) ? "blank" : "issue") ===
                item.issueType &&
              issue.rowNumber > 0,
          )
          .map((issue) => issue.rowNumber),
      );
      const baselineTotal =
        item.baselineRows.size ||
        baselineIssues.filter(
          (issue) =>
            issue.ruleId === item.ruleId &&
            issue.fieldName === item.fieldName &&
            (isBlankIssue(issue) ? "blank" : "issue") ===
              item.issueType,
        ).length;
      const total = Math.max(baselineTotal, unresolvedRows.size);
      const category =
        item.issueType === "blank"
          ? "Blank Values"
          : item.rule?.category ?? "Validation";
      const label =
        item.issueType === "blank"
          ? `Missing ${humanize(item.fieldName)}`
          : item.rule?.ruleName ?? humanize(item.fieldName);
      const completedItem = {
        ...item,
        category,
        label,
        total,
        unresolved: unresolvedRows.size,
        resolved: Math.max(0, total - unresolvedRows.size),
      };
      const group = groups.get(category) ?? [];
      group.push(completedItem);
      groups.set(category, group);
    }

    return [...groups.entries()]
      .map(([category, items]) => ({
        category,
        items: items.sort((left, right) =>
          left.label.localeCompare(right.label),
        ),
        total: items.reduce((sum, item) => sum + item.total, 0),
        unresolved: items.reduce((sum, item) => sum + item.unresolved, 0),
      }))
      .sort((left, right) => {
        const categoryRank = (category) => {
          if (category === "Auto Defaults") return 0;
          if (category === "Blank Values") return 2;
          return 1;
        };
        return categoryRank(left.category) - categoryRank(right.category);
      });
  }, [baselineIssues, currentIssues, ruleCatalog]);

  const blankCandidates = useMemo(() => {
    const candidates = new Map();
    for (const issue of currentIssues) {
      if (
        issue.rowNumber <= 0 ||
        !isBlankIssue(issue) ||
        BULK_FILL_PROTECTED_FIELDS.has(issue.fieldName) ||
        !Object.prototype.hasOwnProperty.call(
          issue.rowData ?? {},
          issue.fieldName,
        )
      ) {
        continue;
      }
      const candidate = candidates.get(issue.fieldName) ?? {
        fieldName: issue.fieldName,
        rows: new Set(),
        preview: [],
        defaultValue: isBlank(issue.suggestedValue)
          ? ""
          : String(issue.suggestedValue),
      };
      if (
        !candidate.defaultValue &&
        !isBlank(issue.suggestedValue)
      ) {
        candidate.defaultValue = String(issue.suggestedValue);
      }
      candidate.rows.add(issue.rowNumber);
      if (candidate.preview.length < 5) {
        candidate.preview.push({
          rowNumber: issue.rowNumber,
          memberId: issue.memberId,
        });
      }
      candidates.set(issue.fieldName, candidate);
    }
    return [...candidates.values()]
      .map((candidate) => ({
        ...candidate,
        count: candidate.rows.size,
      }))
      .sort((left, right) => left.fieldName.localeCompare(right.fieldName));
  }, [currentIssues]);

  const selectedCandidate = blankCandidates.find(
    (candidate) => candidate.fieldName === bulkField,
  );

  const blankIssues = useMemo(
    () =>
      currentIssues.filter(
        (issue) => issue.rowNumber > 0 && isBlankIssue(issue),
      ),
    [currentIssues],
  );

  const visibleIssues = useMemo(() => {
    const tabIssues = issueTab === "blank" ? blankIssues : currentIssues;
    if (selectedRuleKey === "all") return tabIssues;
    const [ruleId, fieldName, issueType] = selectedRuleKey.split(":");
    return tabIssues.filter(
      (issue) =>
        issue.ruleId === ruleId &&
        issue.fieldName === fieldName &&
        (isBlankIssue(issue) ? "blank" : "issue") === issueType,
    );
  }, [blankIssues, currentIssues, issueTab, selectedRuleKey]);

  const selectedDetail = useMemo(() => {
    if (selectedRuleKey === "all") return null;
    const [ruleId, fieldName, issueType] = selectedRuleKey.split(":");
    const meta = getDetailRuleMeta(ruleId, fieldName);
    if (!meta || !issueType) return null;
    return { ruleId, fieldName, issueType, label: meta.label };
  }, [selectedRuleKey]);

  const selectedBlankField = useMemo(() => {
    if (selectedRuleKey === "all") return null;
    const [ruleId, fieldName, issueType] = selectedRuleKey.split(":");
    if (issueType !== "blank" || !fieldName) return null;
    return { ruleId, fieldName };
  }, [selectedRuleKey]);

  /** Prefer the Blank Values rule currently selected in the navigator. */
  const orderedBlankCandidates = useMemo(() => {
    if (!selectedBlankField) return blankCandidates;
    const preferred = blankCandidates.find(
      (candidate) => candidate.fieldName === selectedBlankField.fieldName,
    );
    if (!preferred) return blankCandidates;
    return [
      preferred,
      ...blankCandidates.filter(
        (candidate) => candidate.fieldName !== preferred.fieldName,
      ),
    ];
  }, [blankCandidates, selectedBlankField]);

  const detailIssues = useMemo(() => {
    if (!selectedDetail) return [];
    return currentIssues.filter(
      (issue) =>
        issue.ruleId === selectedDetail.ruleId &&
        issue.fieldName === selectedDetail.fieldName &&
        (isBlankIssue(issue) ? "blank" : "issue") ===
          selectedDetail.issueType,
    );
  }, [currentIssues, selectedDetail]);

  const detailAutofixCount = useMemo(
    () => detailIssues.filter((issue) => issue.autoFixAvailable).length,
    [detailIssues],
  );

  /** Detail-table rows respect the Detected Issues All/Blank tabs. */
  const detailVisibleIssues = useMemo(() => {
    if (issueTab === "blank") {
      return detailIssues.filter(isBlankIssue);
    }
    return detailIssues;
  }, [detailIssues, issueTab]);

  function refreshFromResponse(response, successMessage) {
    if (response?.result) {
      saveValidationResult(response.result);
      setResult(response.result);
    }
    if (successMessage) setMessage(successMessage);
  }

  async function handleAcceptDetail(issue) {
    setBusyKey(`${issue.ruleId}:${issue.rowNumber}:apply`);
    setError("");
    setMessage("");
    try {
      const response = await applyIssueAutoFix(issue.ruleId, issue.rowNumber);
      refreshFromResponse(response, "Suggested value applied.");
    } catch (requestError) {
      setError(
        getApiErrorMessage(requestError, "Could not apply suggested value."),
      );
    } finally {
      setBusyKey(null);
    }
  }

  async function handleApplyAllDetail() {
    if (!selectedDetail) return;
    setBusyKey(`rule:${selectedDetail.ruleId}`);
    setError("");
    setMessage("");
    try {
      const response = await applyRuleAutoFix(selectedDetail.ruleId);
      refreshFromResponse(
        response,
        `All suggested ${selectedDetail.label.toLowerCase()} values applied.`,
      );
    } catch (requestError) {
      setError(
        getApiErrorMessage(requestError, "Could not apply suggested values."),
      );
    } finally {
      setBusyKey(null);
    }
  }

  function startDetailEdit(issue) {
    setEditingKey(`${issue.ruleId}:${issue.rowNumber}:${issue.fieldName}`);
    setEditValue(issue.suggestedValue ?? issue.currentValue ?? "");
    setError("");
  }

  async function saveDetailEdit(issue) {
    setBusyKey(`${issue.ruleId}:${issue.rowNumber}:edit`);
    setError("");
    setMessage("");
    try {
      const response = await applyManualEdit(
        issue.rowNumber,
        issue.fieldName,
        editValue,
      );
      refreshFromResponse(response, "Value updated.");
      setEditingKey(null);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Could not save edit."));
    } finally {
      setBusyKey(null);
    }
  }

  // Keep top cards in sync with remaining issues after Accept / Fill / Edit.
  const summary = useMemo(() => {
    if (!result?.summary) return null;
    const base = result.summary;
    const issues = (result.affectedRows || []).filter(
      (issue) => issue.rowNumber > 0,
    );
    const isBlank = (issue) =>
      issue.issueType === "blank" ||
      issue.currentValue == null ||
      String(issue.currentValue).trim() === "";

    const blankWarnings = issues.filter(isBlank).length;
    const otherWarnings = issues.filter(
      (issue) =>
        !isBlank(issue) &&
        issue.ruleId !== "email_format" &&
        issue.severity === "Warning",
    ).length;
    const emailCritical = issues.filter(
      (issue) => issue.ruleId === "email_format",
    ).length;
    const otherCritical = issues.filter(
      (issue) =>
        issue.ruleId !== "email_format" &&
        !isBlank(issue) &&
        (issue.severity === "Error" || issue.severity === "Critical"),
    ).length;
    const rowsWithIssues = new Set(issues.map((issue) => issue.rowNumber)).size;

    return {
      ...base,
      warnings: blankWarnings + otherWarnings,
      criticalErrors: emailCritical + otherCritical,
      valid: Math.max(0, (base.totalRecords || 0) - rowsWithIssues),
    };
  }, [result]);

  if (!result || !summary) return null;

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
    {
      label: "Warnings",
      value: summary.warnings,
      caption: "Blank values & soft issues",
      icon: AlertTriangle,
      style:
        "border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/20",
      valueStyle: "text-amber-700 dark:text-amber-400",
      iconStyle: "bg-white/80 text-amber-600 dark:bg-amber-950",
    },
    {
      label: "Critical Errors",
      value: summary.criticalErrors,
      caption: "Email & blocking errors",
      icon: CircleAlert,
      style:
        "border-rose-200 bg-rose-50/70 dark:border-rose-900/50 dark:bg-rose-950/20",
      valueStyle: "text-rose-700 dark:text-rose-400",
      iconStyle: "bg-white/80 text-rose-600 dark:bg-rose-950",
    },
  ];

  const openBulkFill = () => {
    const preferred =
      (selectedBlankField &&
        orderedBlankCandidates.find(
          (candidate) =>
            candidate.fieldName === selectedBlankField.fieldName,
        )) ||
      orderedBlankCandidates[0];
    setBulkField(preferred?.fieldName ?? "");
    setBulkValue(preferred?.defaultValue ?? "");
    setError("");
    setMessage("");
    setShowBulkFill(true);
  };

  const handleSelectRule = (ruleKey) => {
    setSelectedRuleKey(ruleKey);
    if (ruleKey !== "all" && ruleKey.endsWith(":blank")) {
      setIssueTab("blank");
    }
  };

  const closeBulkFill = () => {
    if (isApplyingBulk) return;
    setShowBulkFill(false);
    setBulkValue("");
    setError("");
  };

  const applyBulkFill = async () => {
    if (!selectedCandidate || !bulkValue.trim()) return;
    setIsApplyingBulk(true);
    setError("");
    setMessage("");
    try {
      const response = await bulkFillBlankValues(
        selectedCandidate.fieldName,
        bulkValue.trim(),
      );
      setResult(response.result);
      setSelectedRuleKey("all");
      setMessage(response.message);
      setShowBulkFill(false);
      setBulkValue("");
    } catch (requestError) {
      setError(
        getApiErrorMessage(
          requestError,
          "Blank values could not be filled.",
        ),
      );
    } finally {
      setIsApplyingBulk(false);
    }
  };

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
            Resolve validation issues and confirm the dataset before import.
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
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className={`flex min-h-28 items-start justify-between rounded-2xl border p-4 shadow-sm ${card.style}`}
          >
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
      <div className="grid items-start gap-5 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <RuleNavigator
          groups={navigatorGroups}
          score={summary.validationScore}
          unresolvedIssues={currentIssues.length}
          unresolvedRows={
            new Set(
              currentIssues
                .filter((issue) => issue.rowNumber > 0)
                .map((issue) => issue.rowNumber),
            ).size
          }
          selectedRuleKey={selectedRuleKey}
          collapsedCategories={collapsedCategories}
          onSelectRule={handleSelectRule}
          onToggleCategory={(category) =>
            setCollapsedCategories((current) => {
              const next = new Set(current);
              if (next.has(category)) next.delete(category);
              else next.add(category);
              return next;
            })
          }
        />

        <main className="min-w-0 space-y-4">
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <Filter size={16} className="text-indigo-600" />
                  <h2 className="font-semibold text-slate-950 dark:text-white">
                    Detected Issues
                  </h2>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {(selectedDetail
                    ? detailVisibleIssues.length
                    : visibleIssues.length
                  ).toLocaleString()}{" "}
                  issue
                  {(selectedDetail
                    ? detailVisibleIssues.length
                    : visibleIssues.length) === 1
                    ? ""
                    : "s"}{" "}
                  shown
                  {selectedRuleKey === "all" ? "" : " for the selected rule"}.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedRuleKey !== "all" ? (
                  <Button
                    variant="secondary"
                    onClick={() => setSelectedRuleKey("all")}
                  >
                    Clear rule filter
                  </Button>
                ) : null}
                {selectedDetail && detailAutofixCount > 0 ? (
                  <Button
                    variant="secondary"
                    className="gap-2"
                    disabled={busyKey === `rule:${selectedDetail.ruleId}`}
                    onClick={handleApplyAllDetail}
                  >
                    <Wand2 size={16} />
                    Apply all suggested
                  </Button>
                ) : null}
                {issueTab === "blank" || selectedBlankField ? (
                  <Button
                    className="gap-2 bg-indigo-700 hover:bg-indigo-600 dark:bg-indigo-600 dark:text-white"
                    disabled={!blankCandidates.length}
                    onClick={openBulkFill}
                  >
                    <WandSparkles size={16} />
                    Fill Missing Values
                  </Button>
                ) : null}
              </div>
            </div>

            <div className="flex border-b border-slate-200 px-4 dark:border-slate-800">
              {[
                ["all", "All Issues", currentIssues.length],
                ["blank", "Blank Values", blankIssues.length],
              ].map(([value, label, count]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setIssueTab(value)}
                  className={`border-b-2 px-3 py-3 text-sm font-medium transition ${
                    issueTab === value
                      ? "border-indigo-600 text-indigo-700 dark:text-indigo-300"
                      : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  {label}
                  <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">
                    {Number(count).toLocaleString()}
                  </span>
                </button>
              ))}
            </div>

            {selectedDetail &&
            detailIssues.length > 0 &&
            detailAutofixCount === 0 ? (
              <div className="mx-4 mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                Auto Apply: Disabled — No automatic correction exists. Manual
                review required for {selectedDetail.label} rules.
              </div>
            ) : null}

            {selectedDetail ? (
              <div className="w-full overflow-hidden">
                <table className="w-full table-fixed text-left text-sm">
                  <colgroup>
                    <col className="w-[12%]" />
                    <col className="w-[16%]" />
                    <col className="w-[26%]" />
                    <col className="w-[26%]" />
                    <col className="w-[20%]" />
                  </colgroup>
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-950/50 dark:text-slate-400">
                    <tr>
                      <th className="px-3 py-3 font-semibold">Row</th>
                      <th className="px-3 py-3 font-semibold">
                        Affected Field
                      </th>
                      <th className="px-3 py-3 font-semibold">
                        Current Value
                      </th>
                      <th className="px-3 py-3 font-semibold">
                        Suggested Value
                      </th>
                      <th className="px-3 py-3 font-semibold">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {detailVisibleIssues.length === 0 ? (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-4 py-10 text-center text-slate-500"
                        >
                          No issues for this rule in the current view.
                        </td>
                      </tr>
                    ) : (
                      detailVisibleIssues.map((issue) => {
                        const rowKey = `${issue.ruleId}:${issue.rowNumber}:${issue.fieldName}`;
                        const isEditing = editingKey === rowKey;
                        const applyBusy =
                          busyKey ===
                          `${issue.ruleId}:${issue.rowNumber}:apply`;
                        const editBusy =
                          busyKey ===
                          `${issue.ruleId}:${issue.rowNumber}:edit`;
                        return (
                          <tr key={rowKey} className="align-top">
                            <td className="px-3 py-3">
                              <div className="font-semibold text-slate-900 dark:text-white">
                                #{issue.rowNumber}
                              </div>
                              <div className="truncate text-xs text-slate-500">
                                {issue.memberId
                                  ? `ID: ${issue.memberId}`
                                  : "ID: —"}
                              </div>
                            </td>
                            <td className="px-3 py-3">
                              <div className="flex items-start gap-2">
                                <span
                                  className={`mt-0.5 h-8 w-1 shrink-0 rounded-full ${severityBar(issue.severity)}`}
                                />
                                <div className="min-w-0">
                                  <div className="truncate font-medium text-slate-800 dark:text-slate-100">
                                    {issue.fieldName}
                                  </div>
                                  <div className="truncate text-xs text-slate-500">
                                    {selectedDetail.label}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-3">
                              <div className="break-all text-sm text-slate-700 dark:text-slate-200">
                                {issue.currentValue ?? (
                                  <span className="text-slate-400">
                                    (blank)
                                  </span>
                                )}
                              </div>
                              {isChangeNeed(issue) && !isEditing ? (
                                <div className="mt-1 flex items-center gap-1 text-[11px] text-rose-600 dark:text-rose-400">
                                  <AlertTriangle size={12} />
                                  Change need
                                </div>
                              ) : null}
                            </td>
                            <td className="px-3 py-3">
                              {isEditing ? (
                                <input
                                  type="text"
                                  value={editValue}
                                  onChange={(e) =>
                                    setEditValue(e.target.value)
                                  }
                                  autoFocus
                                  className="w-full rounded-lg border border-indigo-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 shadow-sm outline-none ring-2 ring-indigo-100 focus:border-indigo-400 dark:border-indigo-700 dark:bg-slate-950 dark:text-white dark:ring-indigo-950"
                                />
                              ) : issue.suggestedValue != null ? (
                                <div className="break-all text-sm font-medium text-slate-900 dark:text-slate-100">
                                  {issue.suggestedValue}
                                </div>
                              ) : (
                                <span className="text-sm text-slate-400">
                                  —
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-3">
                              <div className="flex flex-wrap gap-1.5">
                                {isEditing ? (
                                  <>
                                    <ActionButton
                                      variant="primary"
                                      disabled={editBusy}
                                      onClick={() => saveDetailEdit(issue)}
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
                                    <ActionButton
                                      className="w-20"
                                      onClick={() => startDetailEdit(issue)}
                                    >
                                      <Pencil size={12} />
                                      Edit
                                    </ActionButton>
                                    {issue.autoFixAvailable ? (
                                      <ActionButton
                                        className="w-20"
                                        variant="success"
                                        disabled={applyBusy}
                                        onClick={() =>
                                          handleAcceptDetail(issue)
                                        }
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
            ) : (
              <div className="max-h-[620px] divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800">
                {visibleIssues.map((issue) => (
                  <div
                    key={`${issue.ruleId}-${issue.fieldName}-${issue.rowNumber}`}
                    className="grid gap-3 p-4 text-sm transition hover:bg-slate-50 sm:grid-cols-[5rem_1fr_1fr_auto] sm:items-center dark:hover:bg-slate-800/50"
                  >
                    <span className="font-medium text-slate-500">
                      {issue.rowNumber > 0 ? `Row ${issue.rowNumber}` : "File"}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-900 dark:text-slate-100">
                        {issue.memberId || issue.ruleName}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {humanize(issue.fieldName)}
                        {isBlankIssue(issue) ? (
                          <span className="ml-2 rounded bg-rose-50 px-1.5 py-0.5 font-semibold text-rose-600 dark:bg-rose-950/50 dark:text-rose-300">
                            {isBlank(issue.currentValue)
                              ? "Blank"
                              : "Becomes blank"}
                          </span>
                        ) : null}
                      </p>
                    </div>
                    <p className="min-w-0 truncate text-slate-600 dark:text-slate-300">
                      {issue.reason}
                    </p>
                    <span
                      className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${
                        issue.severity === "Error"
                          ? "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
                          : issue.severity === "Warning"
                            ? "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300"
                            : "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"
                      }`}
                    >
                      {issue.severity}
                    </span>
                  </div>
                ))}
                {!visibleIssues.length ? (
                  <div className="p-10 text-center">
                    <CheckCircle2
                      size={30}
                      className="mx-auto text-emerald-500"
                    />
                    <p className="mt-3 font-medium text-slate-900 dark:text-white">
                      {issueTab === "blank"
                        ? "No unresolved blank values in this view"
                        : "No unresolved issues in this view"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      Choose another rule or continue to the results.
                    </p>
                  </div>
                ) : null}
              </div>
            )}
          </section>

          {error && !showBulkFill ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
              {error}
            </div>
          ) : null}

          {message ? (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300">
              {message}
            </div>
          ) : null}

          <Button
            className="w-full bg-indigo-700 hover:bg-indigo-600 sm:w-auto dark:bg-indigo-600 dark:text-white"
            onClick={() => navigate("/single-upload/members/results")}
          >
            Finalize Review & Continue
          </Button>
        </main>

      </div>

      {showBulkFill ? (
        <BulkFillDialog
          candidates={orderedBlankCandidates}
          selectedCandidate={selectedCandidate}
          fieldName={bulkField}
          value={bulkValue}
          error={error}
          isApplying={isApplyingBulk}
          onFieldChange={(fieldName) => {
            setBulkField(fieldName);
            setBulkValue(
              orderedBlankCandidates.find(
                (candidate) => candidate.fieldName === fieldName,
              )?.defaultValue ?? "",
            );
            setError("");
          }}
          onValueChange={setBulkValue}
          onClose={closeBulkFill}
          onApply={applyBulkFill}
        />
      ) : null}
    </div>
  );
}

function RuleNavigator({
  groups,
  score,
  unresolvedIssues,
  unresolvedRows,
  selectedRuleKey,
  collapsedCategories,
  onSelectRule,
  onToggleCategory,
}) {
  return (
    <aside className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm xl:sticky xl:top-5 dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-200 p-4 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Layers3 size={17} className="text-indigo-600" />
          <div>
            <h2 className="font-semibold text-slate-950 dark:text-white">
              Rule Navigator
            </h2>
            <p className="text-xs text-slate-500">Status & progress</p>
          </div>
        </div>
        <ValidationScore
          score={score}
          unresolvedIssues={unresolvedIssues}
          unresolvedRows={unresolvedRows}
        />
        <button
          type="button"
          onClick={() => onSelectRule("all")}
          className={`mt-3 flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
            selectedRuleKey === "all"
              ? "bg-indigo-50 font-semibold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"
              : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
          }`}
        >
          <span>All unresolved issues</span>
          <span>{unresolvedIssues}</span>
        </button>
      </div>

      <div className="max-h-[600px] overflow-y-auto p-3">
        {groups.map((group) => {
          const collapsed = collapsedCategories.has(group.category);
          const resolved = Math.max(0, group.total - group.unresolved);
          return (
            <div key={group.category} className="mb-2">
              <button
                type="button"
                onClick={() => onToggleCategory(group.category)}
                className="flex w-full items-center justify-between gap-2 rounded-xl px-2 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <span className="flex min-w-0 items-center gap-2">
                  {collapsed ? (
                    <ChevronRight size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )}
                  <span className="truncate text-sm font-semibold text-slate-800 dark:text-slate-200">
                    {group.category}
                  </span>
                </span>
                <span
                  className={`shrink-0 text-[10px] font-semibold ${
                    group.unresolved === 0
                      ? "text-emerald-600"
                      : "text-slate-500"
                  }`}
                >
                  {resolved}/{group.total} Resolved
                </span>
              </button>
              {!collapsed ? (
                <div className="ml-3 border-l border-slate-200 pl-2 dark:border-slate-700">
                  {group.items.map((item) => {
                    const selected = selectedRuleKey === item.key;
                    return (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => onSelectRule(item.key)}
                        className={`mb-1 flex w-full items-center justify-between gap-2 rounded-lg px-2 py-2 text-left text-xs transition ${
                          selected
                            ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"
                            : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                        }`}
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          {item.unresolved === 0 ? (
                            <CheckCircle2
                              size={13}
                              className="shrink-0 text-emerald-500"
                            />
                          ) : (
                            <CircleAlert
                              size={13}
                              className={`shrink-0 ${
                                item.rule?.severity === "Critical"
                                  ? "text-rose-500"
                                  : "text-amber-500"
                              }`}
                            />
                          )}
                          <span className="truncate">{item.label}</span>
                        </span>
                        <span
                          className={`shrink-0 font-semibold ${
                            item.unresolved === 0
                              ? "text-emerald-600"
                              : "text-rose-600"
                          }`}
                        >
                          {item.unresolved
                            ? `${item.unresolved} Row${item.unresolved === 1 ? "" : "s"}`
                            : "Resolved"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}

function ValidationScore({ score, unresolvedIssues, unresolvedRows }) {
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.max(0, Math.min(100, score)) / 100) * circumference;
  const scoreTone =
    score >= 95
      ? "text-emerald-600"
      : score >= 80
        ? "text-amber-600"
        : "text-rose-600";

  return (
    <div className="mt-4 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
      <div className="relative h-14 w-14 shrink-0">
        <svg className="-rotate-90" viewBox="0 0 52 52">
          <circle
            cx="26"
            cy="26"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            className="text-slate-200 dark:text-slate-700"
          />
          <circle
            cx="26"
            cy="26"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`${scoreTone} transition-all duration-500`}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-slate-900 dark:text-white">
          {Math.round(score)}%
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900 dark:text-white">
          Validation Score
        </p>
        <p className="mt-0.5 text-xs leading-5 text-slate-500">
          {unresolvedIssues
            ? `${unresolvedIssues} issues across ${unresolvedRows} rows`
            : "All validation issues resolved"}
        </p>
      </div>
    </div>
  );
}

function BulkFillDialog({
  candidates,
  selectedCandidate,
  fieldName,
  value,
  error,
  isApplying,
  onFieldChange,
  onValueChange,
  onClose,
  onApply,
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bulk-fill-title"
    >
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-start justify-between border-b border-slate-200 p-5 dark:border-slate-800">
          <div className="flex gap-3">
            <span className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300">
              <Sparkles size={19} />
            </span>
            <div>
              <h2
                id="bulk-fill-title"
                className="font-semibold text-slate-950 dark:text-white"
              >
                Fill Missing Values
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Apply one value only to blank cells in a selected column.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isApplying}
            className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            aria-label="Close bulk fill"
          >
            <X size={17} />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <label className="block">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Column
            </span>
            <select
              value={fieldName}
              onChange={(event) => onFieldChange(event.target.value)}
              disabled={isApplying}
              className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
            >
              {candidates.map((candidate) => (
                <option key={candidate.fieldName} value={candidate.fieldName}>
                  {humanize(candidate.fieldName)} — {candidate.count} blank
                  {candidate.count === 1 ? "" : "s"}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Value for every blank cell
            </span>
            <input
              value={value}
              onChange={(event) => onValueChange(event.target.value)}
              disabled={isApplying}
              placeholder={`Enter ${humanize(fieldName || "column")} value`}
              className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
              autoFocus
            />
          </label>

          {selectedCandidate ? (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 text-sm dark:border-indigo-900/50 dark:bg-indigo-950/25">
              <p className="font-medium text-indigo-900 dark:text-indigo-200">
                {selectedCandidate.count} blank cell
                {selectedCandidate.count === 1 ? "" : "s"} will be updated
              </p>
              <p className="mt-1 text-xs leading-5 text-indigo-700 dark:text-indigo-300">
                Preview rows:{" "}
                {selectedCandidate.preview
                  .map((item) => item.memberId || `Row ${item.rowNumber}`)
                  .join(", ")}
                {selectedCandidate.count > selectedCandidate.preview.length
                  ? ` and ${selectedCandidate.count - selectedCandidate.preview.length} more`
                  : ""}
                .
              </p>
            </div>
          ) : null}

          <p className="text-xs leading-5 text-slate-500">
            Existing values will not be overwritten. The dataset is revalidated
            after this change, and every updated row is recorded in the audit
            log.
          </p>

          {error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
              {error}
            </div>
          ) : null}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-800 dark:bg-slate-950/40">
          <Button
            variant="secondary"
            disabled={isApplying}
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            className="gap-2 bg-indigo-700 hover:bg-indigo-600 dark:bg-indigo-600 dark:text-white"
            disabled={!selectedCandidate || !value.trim() || isApplying}
            onClick={onApply}
          >
            {isApplying ? (
              <LoaderCircle size={16} className="animate-spin" />
            ) : (
              <WandSparkles size={16} />
            )}
            {isApplying
              ? "Applying..."
              : `Apply to ${selectedCandidate?.count ?? 0} blanks`}
          </Button>
        </div>
      </div>
    </div>
  );
}
