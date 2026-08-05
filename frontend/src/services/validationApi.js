import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  withCredentials: true,
  timeout: 120000,
});

const resultKey = "membersValidationResult";

export async function startMembersValidation(file, options = {}) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/members/validate/start", formData, {
    ...options,
  });
  sessionStorage.setItem("uploadedFile", file.name);
  return response.data;
}

export async function getMembersValidationProgress(validationId, options = {}) {
  const response = await api.get(
    `/members/validate/${validationId}/progress`,
    options,
  );
  if (response.data.result) {
    saveValidationResult(response.data.result);
  }
  return response.data;
}

export async function addMissingMandatoryColumns(options = {}) {
  const response = await api.post(
    "/members/file-review/add-missing-columns",
    null,
    options,
  );
  if (response.data.result) {
    saveValidationResult(response.data.result);
  }
  return response.data;
}

export function saveValidationResult(result) {
  sessionStorage.setItem(resultKey, JSON.stringify(result));
}

export function getValidationResult() {
  const stored = sessionStorage.getItem(resultKey);
  return stored ? JSON.parse(stored) : null;
}

async function downloadReport(reportName, format = "csv") {
  const response = await api.get(`/members/report/${reportName}`, {
    params: { format },
    responseType: "blob",
  });
  const disposition = response.headers["content-disposition"] || "";
  const filename =
    disposition.match(/filename="?([^"]+)"?/)?.[1] ||
    `members_validation_${reportName}.${format}`;
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const downloadSummary = (format) => downloadReport("summary", format);
export const downloadAudit = (format) => downloadReport("audit", format);
export const downloadCorrected = (format) =>
  downloadReport("corrected", format);

export function getApiErrorMessage(error, fallback = "Request failed") {
  return error.response?.data?.detail || error.message || fallback;
}
