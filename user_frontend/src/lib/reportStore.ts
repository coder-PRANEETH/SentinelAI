/**
 * Lightweight client-side handoff between report steps. No backend session
 * exists for anonymous reporters, so the in-progress report is kept in
 * sessionStorage between /report/car-breakdown → /report/safe-location → /report/success.
 */
import type { CarBreakdownReport, IncidentSubmissionResult } from "@/types/incident";

const REPORT_KEY = "sentinel:draft_report";
const RESULT_KEY = "sentinel:submission_result";

export function saveDraftReport(report: CarBreakdownReport) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(REPORT_KEY, JSON.stringify(report));
}

export function loadDraftReport(): CarBreakdownReport | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(REPORT_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function saveSubmissionResult(result: IncidentSubmissionResult) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(RESULT_KEY, JSON.stringify(result));
}

export function loadSubmissionResult(): IncidentSubmissionResult | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(RESULT_KEY);
  return raw ? JSON.parse(raw) : null;
}
