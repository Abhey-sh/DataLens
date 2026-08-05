import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleX,
  CloudUpload,
  Database,
  Download,
  Filter,
  LoaderCircle,
  RotateCcw,
  Search,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import {
  applyMemberIssueAutoFix,
  applyMemberManualEdit,
  applyMembersAutoFix,
  downloadErrors,
  getApiErrorMessage,
  getMembersFileRows,
  getValidationResult,
} from "../services/validationService";

const PAGE_SIZE = 50;
const tableColumns = [
  { label: "Member ID", keys: ["userForeignId", "memberId", "studioForeignId"] },
  { label: "First Name", keys: ["firstName", "first_name"] },
  { label: "Last Name", keys: ["lastName", "last_name"] },
  { label: "Email", keys: ["email"] },
  { label: "Phone", keys: ["phone", "phoneNumber", "mobilePhone"] },
  { label: "Gender", keys: ["gender"] },
  { label: "Birth Date", keys: ["birthDate", "birth_date"] },
  { label: "Lead Status", keys: ["leadStatus", "lead_status"] },
];

function getCell(row, keys) {
  const key = keys.find((candidate) =>
    Object.prototype.hasOwnProperty.call(row, candidate),
  );
  return key ? row[key] : null;
}

function percentage(value, total) {
  return total ? `${((value / total) * 100).toFixed(2)}% of total` : "0% of total";
}

export function MembersReviewPage() {
  const navigate = useNavigate();
  const [result, setResult] = useState(() => getValidationResult());
  const [filePage, setFilePage] = useState({
    columns: [],
    rows: [],
    total: 0,
    offset: 0,
    limit: PAGE_SIZE,
  });
  const [pageNumber, setPageNumber] = useState(0);
  const [query, setQuery] = useState("");
  const [searchColumn, setSearchColumn] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeTab, setActiveTab] = useState("all");
  const [selectedFields, setSelectedFields] = useState([]);
  const [expandedRow, setExpandedRow] = useState(null);
  const [expandedRule, setExpandedRule] = useState(null);
  const [editingIssue, setEditingIssue] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [message, setMessage] = useState("");

  const issues = useMemo(() => result?.affectedRows ?? [], [result]);
  const errorIssues = useMemo(
    () => issues.filter((issue) => issue.severity === "Error"),
    [issues],
  );
  const warningIssues = useMemo(
    () => issues.filter((issue) => issue.severity !== "Error"),
    [issues],
  );
  const summary = result?.summary;
  const validationAvailable = Boolean(result);

  useEffect(() => {
    if (!result) {
      navigate("/single-upload/members/upload", { replace: true });
    }
  }, [navigate, result]);

  useEffect(() => {
    if (!validationAvailable) return undefined;
    const controller = new AbortController();
    getMembersFileRows(pageNumber * PAGE_SIZE, PAGE_SIZE, {
      signal: controller.signal,
    })
      .then((page) => {
        setFilePage(page);
        setIsLoading(false);
      })
      .catch((error) => {
        if (error.code !== "ERR_CANCELED") {
          setMessage(getApiErrorMessage(error, "Could not load file rows."));
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, [pageNumber, validationAvailable]);

  const issuesByRow = useMemo(() => {
    const grouped = new Map();
    issues.forEach((issue) => {
      const current = grouped.get(issue.rowNumber) ?? [];
      current.push(issue);
      grouped.set(issue.rowNumber, current);
    });
    return grouped;
  }, [issues]);

  const issueFields = useMemo(
    () => [...new Set(issues.map((issue) => issue.fieldName))].sort(),
    [issues],
  );

  const visibleRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    let candidates;
    if (activeTab === "all") {
      candidates = filePage.rows.map((row, index) => {
        const rowNumber = filePage.offset + index + 1;
        return {
          row,
          rowNumber,
          rowIssues: issuesByRow.get(rowNumber) ?? [],
        };
      });
    } else {
      const tabIssues =
        activeTab === "errors" ? errorIssues : warningIssues;
      const grouped = new Map();
      tabIssues.forEach((issue) => {
        const entry = grouped.get(issue.rowNumber) ?? {
          row: {
            ...(issue.rowData ?? {}),
            userForeignId:
              issue.rowData?.userForeignId ?? issue.memberId,
          },
          rowNumber: issue.rowNumber,
          rowIssues: [],
        };
        entry.row[issue.fieldName] = issue.currentValue;
        entry.rowIssues.push(issue);
        grouped.set(issue.rowNumber, entry);
      });
      candidates = [...grouped.values()];
    }

    return candidates.filter(({ row, rowIssues }) => {
      if (
        selectedFields.length &&
        !rowIssues.some((issue) => selectedFields.includes(issue.fieldName))
      ) {
        return false;
      }
      if (
        statusFilter === "issues" &&
        rowIssues.length === 0
      ) {
        return false;
      }
      if (
        statusFilter === "valid" &&
        rowIssues.length > 0
      ) {
        return false;
      }
      if (!normalizedQuery) return true;
      const values =
        searchColumn === "all"
          ? [
              ...Object.values(row),
              ...rowIssues.flatMap((issue) => [
                issue.ruleName,
                issue.reason,
                issue.fieldName,
              ]),
            ]
          : [row[searchColumn]];
      return values.some((value) =>
        String(value ?? "").toLowerCase().includes(normalizedQuery),
      );
    });
  }, [
    activeTab,
    errorIssues,
    filePage.offset,
    filePage.rows,
    issuesByRow,
    query,
    searchColumn,
    selectedFields,
    statusFilter,
    warningIssues,
  ]);

  if (!result) return null;

  const automaticRules = result.businessRules.filter(
    (rule) => rule.autoFixAvailable,
  );
  const pendingAutomaticIssues = issues.filter(
    (issue) => issue.autoFixAvailable && issue.status !== "Fixed",
  );

  const markIssuesFixed = (predicate) => {
    setResult((current) => ({
      ...current,
      affectedRows: current.affectedRows.map((issue) =>
        predicate(issue)
          ? { ...issue, status: "Fixed", action: "Applied" }
          : issue,
      ),
    }));
  };

  const handleApplyAll = async () => {
    setBusyAction("all");
    setMessage("");
    try {
      for (const rule of automaticRules) {
        await applyMembersAutoFix(rule.ruleId);
      }
      markIssuesFixed((issue) => issue.autoFixAvailable);
      setMessage(`${pendingAutomaticIssues.length} automatic fixes applied.`);
    } catch (error) {
      setMessage(getApiErrorMessage(error, "Could not apply automatic fixes."));
    } finally {
      setBusyAction("");
    }
  };

  const handleAccept = async (issue) => {
    setBusyAction(`${issue.ruleId}-${issue.rowNumber}`);
    setMessage("");
    try {
      await applyMemberIssueAutoFix(issue.ruleId, issue.rowNumber);
      markIssuesFixed(
        (item) =>
          item.ruleId === issue.ruleId && item.rowNumber === issue.rowNumber,
      );
      setMessage(`Fix accepted for row ${issue.rowNumber}.`);
    } catch (error) {
      setMessage(getApiErrorMessage(error, "Could not apply this fix."));
    } finally {
      setBusyAction("");
    }
  };

  const handleSaveEdit = async () => {
    if (!editingIssue || !editValue.trim()) return;
    setBusyAction("edit");
    try {
      await applyMemberManualEdit(
        editingIssue.rowNumber,
        editingIssue.fieldName,
        editValue.trim(),
      );
      setResult((current) => ({
        ...current,
        affectedRows: current.affectedRows.map((issue) =>
          issue.rowNumber === editingIssue.rowNumber &&
          issue.fieldName === editingIssue.fieldName
            ? {
                ...issue,
                currentValue: editValue.trim(),
                status: "Fixed",
                action: "Edited",
              }
            : issue,
        ),
      }));
      setEditingIssue(null);
      setEditValue("");
      setMessage(`Row ${editingIssue.rowNumber} was updated.`);
    } catch (error) {
      setMessage(getApiErrorMessage(error, "Could not save this edit."));
    } finally {
      setBusyAction("");
    }
  };

  const resetFilters = () => {
    setQuery("");
    setSearchColumn("all");
    setStatusFilter("all");
    setSelectedFields([]);
  };

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
      caption: percentage(summary.warnings, summary.totalRecords),
      icon: AlertTriangle,
      style:
        "border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/20",
      valueStyle: "text-amber-600 dark:text-amber-400",
      iconStyle: "bg-white/80 text-amber-500 dark:bg-amber-950",
    },
    {
      label: "Errors",
      value: summary.criticalErrors,
      caption: percentage(summary.criticalErrors, summary.totalRecords),
      icon: CircleX,
      style:
        "border-rose-200 bg-rose-50/70 dark:border-rose-900/50 dark:bg-rose-950/20",
      valueStyle: "text-rose-600 dark:text-rose-400",
      iconStyle: "bg-white/80 text-rose-500 dark:bg-rose-950",
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
            Review & Fix Members Data
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Review the validation results and fix issues before finalizing.
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

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <main className="min-w-0 space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
              <label className="flex min-w-48 flex-1 items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 dark:border-slate-700">
                <Search size={15} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search by name, email, or any value..."
                  className="min-w-0 flex-1 bg-transparent outline-none"
                />
              </label>
              <select
                value={searchColumn}
                onChange={(event) => setSearchColumn(event.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              >
                <option value="all">All Columns</option>
                {filePage.columns.map((column) => (
                  <option key={column} value={column}>
                    {column}
                  </option>
                ))}
              </select>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              >
                <option value="all">All Status</option>
                <option value="valid">Valid</option>
                <option value="issues">Has Issues</option>
              </select>
              <div className="relative">
                <Button
                  variant="secondary"
                  className="w-full gap-2 rounded-lg lg:w-auto"
                  onClick={() => setShowFilters((open) => !open)}
                >
                  <Filter size={15} />
                  Filters{selectedFields.length ? ` (${selectedFields.length})` : ""}
                </Button>
                {showFilters ? (
                  <div className="absolute right-0 z-30 mt-2 max-h-72 w-60 overflow-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                    <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Columns containing issues
                    </p>
                    {issueFields.map((field) => (
                      <label
                        key={field}
                        className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                      >
                        <input
                          type="checkbox"
                          checked={selectedFields.includes(field)}
                          onChange={() =>
                            setSelectedFields((current) =>
                              current.includes(field)
                                ? current.filter((item) => item !== field)
                                : [...current, field],
                            )
                          }
                          className="accent-indigo-600"
                        />
                        {field}
                      </label>
                    ))}
                  </div>
                ) : null}
              </div>
              <button
                type="button"
                onClick={resetFilters}
                className="inline-flex items-center justify-center gap-1.5 px-2 py-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white"
              >
                <RotateCcw size={14} />
                Clear
              </button>
              <Button
                className="gap-2 bg-indigo-700 hover:bg-indigo-600 dark:bg-indigo-600 dark:text-white"
                disabled={busyAction === "all" || !pendingAutomaticIssues.length}
                onClick={handleApplyAll}
              >
                {busyAction === "all" ? (
                  <LoaderCircle size={15} className="animate-spin" />
                ) : (
                  <WandSparkles size={15} />
                )}
                Apply All Fixes
              </Button>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 dark:border-slate-800">
              <div className="flex">
                {[
                  ["all", "All Records", summary.totalRecords],
                  ["errors", "Errors", errorIssues.length],
                  ["warnings", "Warnings", warningIssues.length],
                ].map(([value, label, count]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setActiveTab(value)}
                    className={`border-b-2 px-3 py-4 text-sm font-medium ${
                      activeTab === value
                        ? "border-indigo-600 text-indigo-700 dark:text-indigo-300"
                        : "border-transparent text-slate-500"
                    }`}
                  >
                    {label}
                    <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">
                      {Number(count).toLocaleString()}
                    </span>
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="text-emerald-600">
                  {issues.filter((issue) => issue.status === "Fixed").length} fixes
                  applied
                </span>
                <button
                  type="button"
                  onClick={() => downloadErrors("csv")}
                  className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400"
                >
                  <Download size={13} />
                  Download
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-[980px] w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-950/40">
                  <tr>
                    <th className="w-10 px-3 py-3" />
                    <th className="px-3 py-3 font-medium">Row</th>
                    {tableColumns.map((column) => (
                      <th key={column.label} className="px-3 py-3 font-medium">
                        {column.label}
                      </th>
                    ))}
                    <th className="px-3 py-3 text-center font-medium">Issues</th>
                    <th className="w-10 px-3 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {visibleRows.map(({ row, rowNumber, rowIssues }) => {
                    const isExpanded = expandedRow === rowNumber;
                    return (
                      <RowsWithDetails
                        key={rowNumber}
                        row={row}
                        rowNumber={rowNumber}
                        rowIssues={rowIssues}
                        isExpanded={isExpanded}
                        busyAction={busyAction}
                        editingIssue={editingIssue}
                        editValue={editValue}
                        onToggle={() =>
                          setExpandedRow(isExpanded ? null : rowNumber)
                        }
                        onAccept={handleAccept}
                        onStartEdit={(issue) => {
                          setEditingIssue(issue);
                          setEditValue(issue.currentValue ?? "");
                        }}
                        onEditValue={setEditValue}
                        onSaveEdit={handleSaveEdit}
                        onCancelEdit={() => setEditingIssue(null)}
                      />
                    );
                  })}
                </tbody>
              </table>
              {activeTab === "all" && isLoading ? (
                <div className="flex items-center justify-center gap-2 p-10 text-sm text-slate-500">
                  <LoaderCircle size={16} className="animate-spin" />
                  Loading file rows—errors are already available in the Errors tab.
                </div>
              ) : null}
              {!(activeTab === "all" && isLoading) && !visibleRows.length ? (
                <p className="p-10 text-center text-sm text-slate-500">
                  No records match this view.
                </p>
              ) : null}
            </div>

            <div className="border-t border-slate-200 px-4 py-3 dark:border-slate-800">
              {activeTab === "all" ? (
                <div className="flex items-center justify-between">
                  <p className="text-xs text-slate-500">
                    Rows {filePage.total ? filePage.offset + 1 : 0}–
                    {Math.min(
                      filePage.offset + filePage.rows.length,
                      filePage.total,
                    )}{" "}
                    of {filePage.total.toLocaleString()}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      disabled={!pageNumber || isLoading}
                      onClick={() => {
                        setIsLoading(true);
                        setPageNumber((page) => page - 1);
                      }}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={
                        filePage.offset + filePage.rows.length >= filePage.total ||
                        isLoading
                      }
                      onClick={() => {
                        setIsLoading(true);
                        setPageNumber((page) => page + 1);
                      }}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500">
                  Showing {visibleRows.length.toLocaleString()} affected records
                </p>
              )}
            </div>
          </div>
          {message ? (
            <p className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
              {message}
            </p>
          ) : null}
        </main>

        <aside className="flex max-h-[760px] flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2">
            <ShieldCheck size={17} className="text-slate-600" />
            <h2 className="font-semibold text-slate-900 dark:text-white">
              Business Rules
            </h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Summary of rules applied for this import
          </p>
          <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
            {result.businessRules.map((rule) => {
              const open = expandedRule === rule.ruleId;
              return (
                <div
                  key={rule.ruleId}
                  className="rounded-xl border border-slate-200 dark:border-slate-700"
                >
                  <button
                    type="button"
                    onClick={() => setExpandedRule(open ? null : rule.ruleId)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-3 text-left"
                  >
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                      {rule.ruleName}
                    </span>
                    <span className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          rule.severity === "Critical"
                            ? "bg-rose-50 text-rose-600 dark:bg-rose-950/40"
                            : "bg-amber-50 text-amber-600 dark:bg-amber-950/40"
                        }`}
                      >
                        {rule.affectedRows}
                      </span>
                      {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </span>
                  </button>
                  {open ? (
                    <div className="border-t border-slate-100 px-3 py-3 text-xs text-slate-500 dark:border-slate-800">
                      <p>{rule.businessLogic}</p>
                      <p className="mt-2">
                        {rule.autoFixAvailable
                          ? `Auto fix: ${rule.defaultValue ?? "Configured rule"}`
                          : "Manual review required"}
                      </p>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
          <Button
            className="mt-4 w-full bg-indigo-700 hover:bg-indigo-600 dark:bg-indigo-600 dark:text-white"
            onClick={() => navigate("/single-upload/members/results")}
          >
            Finalize Review & Continue
          </Button>
        </aside>
      </div>
    </div>
  );
}

function RowsWithDetails({
  row,
  rowNumber,
  rowIssues,
  isExpanded,
  busyAction,
  editingIssue,
  editValue,
  onToggle,
  onAccept,
  onStartEdit,
  onEditValue,
  onSaveEdit,
  onCancelEdit,
}) {
  const issueTone = rowIssues.some((issue) => issue.severity === "Error")
    ? "text-rose-600"
    : rowIssues.length
      ? "text-amber-600"
      : "text-emerald-600";
  return (
    <>
      <tr className={isExpanded ? "bg-rose-50/50 dark:bg-rose-950/10" : ""}>
        <td className="px-3 py-3">
          <input type="checkbox" className="accent-indigo-600" />
        </td>
        <td className="px-3 py-3 text-slate-500">{rowNumber}</td>
        {tableColumns.map((column) => (
          <td
            key={column.label}
            className="max-w-36 truncate px-3 py-3 text-slate-700 dark:text-slate-300"
            title={getCell(row, column.keys) ?? ""}
          >
            {getCell(row, column.keys) || "—"}
          </td>
        ))}
        <td className={`px-3 py-3 text-center font-semibold ${issueTone}`}>
          {rowIssues.length}
        </td>
        <td className="px-3 py-3">
          <button type="button" onClick={onToggle} disabled={!rowIssues.length}>
            {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          </button>
        </td>
      </tr>
      {isExpanded
        ? rowIssues.map((issue) => {
            const editing =
              editingIssue?.rowNumber === issue.rowNumber &&
              editingIssue?.fieldName === issue.fieldName;
            return (
              <tr key={`${issue.ruleId}-${issue.fieldName}`}>
                <td colSpan={12} className="bg-rose-50/60 px-5 py-3 dark:bg-rose-950/10">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <CircleX size={15} className="mt-0.5 shrink-0 text-rose-500" />
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-800 dark:text-slate-200">
                            {issue.ruleName}
                          </span>
                          <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-medium text-rose-600 dark:bg-rose-950/50">
                            {issue.severity}
                          </span>
                        </div>
                        <p className="mt-1 text-slate-500">{issue.reason}</p>
                        <p className="mt-1 text-slate-500">
                          Suggested:{" "}
                          <strong className="text-slate-700 dark:text-slate-300">
                            {issue.suggestedValue ?? "Manual review required"}
                          </strong>
                        </p>
                      </div>
                    </div>
                    {editing ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={editValue}
                          onChange={(event) => onEditValue(event.target.value)}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"
                          autoFocus
                        />
                        <Button disabled={busyAction === "edit"} onClick={onSaveEdit}>
                          Save
                        </Button>
                        <Button variant="ghost" onClick={onCancelEdit}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="flex shrink-0 gap-2">
                        {issue.autoFixAvailable && issue.status !== "Fixed" ? (
                          <Button
                            className="bg-indigo-700 hover:bg-indigo-600 dark:bg-indigo-600 dark:text-white"
                            disabled={
                              busyAction === `${issue.ruleId}-${issue.rowNumber}`
                            }
                            onClick={() => onAccept(issue)}
                          >
                            Accept
                          </Button>
                        ) : null}
                        <Button
                          variant="secondary"
                          onClick={() => onStartEdit(issue)}
                        >
                          Edit
                        </Button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            );
          })
        : null}
    </>
  );
}
