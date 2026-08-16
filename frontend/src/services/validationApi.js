import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  withCredentials: true,
  timeout: 120000,
});

const DOMAINS = ["members", "assets"];

/**
 * Build a client for one import domain. Every domain exposes the same
 * endpoints under its own `/api/{domain}` prefix and keeps its result in its
 * own session storage key, so two datasets never overwrite each other.
 */
function createValidationApi(domain) {
  const resultKey = `${domain}ValidationResult`;
  const fileNameKey = `${domain}UploadedFile`;

  function saveValidationResult(result) {
    sessionStorage.setItem(resultKey, JSON.stringify(result));
  }

  function getValidationResult() {
    const stored = sessionStorage.getItem(resultKey);
    return stored ? JSON.parse(stored) : null;
  }

  function clearSession() {
    sessionStorage.removeItem(resultKey);
    sessionStorage.removeItem(fileNameKey);
  }

  function storeResult(response) {
    if (response.data.result) {
      saveValidationResult(response.data.result);
    }
    return response.data;
  }

  async function startValidation(file, options = {}) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post(
      `/${domain}/validate/start`,
      formData,
      options,
    );
    sessionStorage.setItem(fileNameKey, file.name);
    return response.data;
  }

  async function getValidationProgress(validationId, options = {}) {
    const response = await api.get(
      `/${domain}/validate/${validationId}/progress`,
      options,
    );
    return storeResult(response);
  }

  async function addMissingMandatoryColumns(options = {}) {
    const response = await api.post(
      `/${domain}/file-review/add-missing-columns`,
      null,
      options,
    );
    return storeResult(response);
  }

  async function bulkFillBlankValues(fieldName, value, options = {}) {
    const response = await api.post(
      `/${domain}/bulk-fill`,
      { fieldName, value },
      options,
    );
    return storeResult(response);
  }

  async function applyIssueAutoFix(ruleId, rowNumber, options = {}) {
    const response = await api.post(
      `/${domain}/auto-fix/issue`,
      { ruleId, rowNumber },
      options,
    );
    return storeResult(response);
  }

  async function applyRuleAutoFix(ruleId, issueType, options = {}) {
    const response = await api.post(
      `/${domain}/auto-fix`,
      { ruleId, issueType },
      options,
    );
    return storeResult(response);
  }

  async function applyManualEdit(rowNumber, fieldName, value, options = {}) {
    const response = await api.post(
      `/${domain}/edit`,
      { rowNumber, fieldName, value },
      options,
    );
    return storeResult(response);
  }

  async function downloadReport(reportName, format = "csv") {
    const response = await api.get(`/${domain}/report/${reportName}`, {
      params: { format },
      responseType: "blob",
    });
    const disposition = response.headers["content-disposition"] || "";
    const filename =
      disposition.match(/filename="?([^"]+)"?/)?.[1] ||
      `${domain}_validation_${reportName}.${format}`;
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return {
    addMissingMandatoryColumns,
    applyIssueAutoFix,
    applyManualEdit,
    applyRuleAutoFix,
    bulkFillBlankValues,
    clearSession,
    downloadAudit: (format) => downloadReport("audit", format),
    downloadCorrected: (format) => downloadReport("corrected", format),
    downloadErrors: (format) => downloadReport("errors", format),
    downloadRemoved: (format) => downloadReport("removed", format),
    downloadSummary: (format) => downloadReport("summary", format),
    getValidationProgress,
    getValidationResult,
    saveValidationResult,
    startValidation,
  };
}

const clients = Object.fromEntries(
  DOMAINS.map((domain) => [domain, createValidationApi(domain)]),
);

export const membersApi = clients.members;
export const assetsApi = clients.assets;

/** Drop every stored validation result, whatever the import domain. */
export function clearValidationSession() {
  Object.values(clients).forEach((client) => client.clearSession());
}

export function getApiErrorMessage(error, fallback = "Request failed") {
  return error.response?.data?.detail || error.message || fallback;
}

export const {
  addMissingMandatoryColumns,
  applyIssueAutoFix,
  applyManualEdit,
  applyRuleAutoFix,
  bulkFillBlankValues,
  downloadAudit,
  downloadCorrected,
  downloadSummary,
  getValidationResult,
  saveValidationResult,
} = membersApi;
export const startMembersValidation = membersApi.startValidation;
export const getMembersValidationProgress = membersApi.getValidationProgress;
