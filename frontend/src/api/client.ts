import { AuditLogItem, JobDetail, VerificationReport } from "../types";

function getApiBase(): string {
  const rawBase = ((import.meta as any).env?.VITE_API_BASE_URL as string | undefined)?.trim();

  if (!rawBase) {
    throw new Error("VITE_API_BASE_URL must be configured for the KYC frontend.");
  }

  const url = new URL(rawBase);
  if (url.protocol !== "https:") {
    throw new Error("Insecure API endpoint rejected. Production API traffic must use HTTPS.");
  }

  return url.toString().replace(/\/$/, "");
}

export const API_BASE = getApiBase();

const secureFetchOptions: RequestInit = {
  credentials: "include",
  cache: "no-store",
};

async function handleResponse<T>(res: Response, defaultErrorMsg: string): Promise<T> {
  if (!res.ok) {
    let detail = "";
    try {
      const errJson = await res.json();
      detail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail ? `${defaultErrorMsg}: ${detail}` : defaultErrorMsg);
  }
  return res.json();
}

export async function createJob(externalReference?: string): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/jobs`, {
    ...secureFetchOptions,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ external_reference: externalReference || `JOB-${Date.now()}` }),
  });
  return handleResponse<{ job_id: string; status: string }>(res, "Failed to create job");
}

export async function uploadDocument(
  jobId: string,
  file: File,
  role: "primary" | "supporting",
  documentTypeHint?: string
): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("role", role);
  if (documentTypeHint) formData.append("document_type_hint", documentTypeHint);

  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/documents`, {
    ...secureFetchOptions,
    method: "POST",
    body: formData,
  });
  return handleResponse<any>(res, `Failed to upload ${role} document`);
}

export async function triggerProcessing(jobId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/process`, {
    ...secureFetchOptions,
    method: "POST",
  });
  return handleResponse<any>(res, "Failed to start processing");
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`, secureFetchOptions);
  return handleResponse<JobDetail>(res, "Failed to fetch job details");
}

export async function fetchVerificationResult(jobId: string): Promise<VerificationReport> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/result`, secureFetchOptions);
  return handleResponse<VerificationReport>(res, "Verification report not ready");
}

export async function fetchAuditLogs(limit: number = 50): Promise<AuditLogItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/audit/logs?limit=${limit}`, secureFetchOptions);
  return handleResponse<AuditLogItem[]>(res, "Failed to fetch audit logs");
}

export function getSSEEventSourceUrl(jobId: string): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/events/stream`;
}
