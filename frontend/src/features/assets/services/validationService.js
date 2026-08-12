import { assetsApi, getApiErrorMessage } from "../../../services/validationApi";

export const {
  addMissingMandatoryColumns,
  applyIssueAutoFix,
  applyManualEdit,
  applyRuleAutoFix,
  bulkFillBlankValues,
  downloadAudit,
  downloadCorrected,
  downloadRemoved,
  downloadSummary,
  getValidationProgress,
  getValidationResult,
  saveValidationResult,
  startValidation,
} = assetsApi;

export { getApiErrorMessage };
