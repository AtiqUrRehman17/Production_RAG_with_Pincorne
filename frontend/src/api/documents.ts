import { API_BASE, ApiError, getAccessToken, refreshSession, request } from "./client";
import type { DocumentInfo, ErrorBody, Job, Page, PageParams } from "./types";

export const ALLOWED_EXTENSIONS = ["pdf", "docx", "txt"]; // the backend's ALLOWED_EXTENSIONS
export const MAX_FILE_SIZE_MB = 50; // the backend's MAX_FILE_SIZE_MB

export function listDocuments(params: PageParams = {}): Promise<Page<DocumentInfo>> {
  return request("/documents", { query: { ...params } });
}

export function getDocument(documentId: string): Promise<DocumentInfo> {
  return request(`/documents/${encodeURIComponent(documentId)}`);
}

/** Quick checks run at once; the returned job ingests the file in the background. */
export function uploadDocument(file: File, signal?: AbortSignal): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  return request("/documents", { body: form, signal });
}

function sendUpload(file: File, onProgress: (fraction: number) => void): Promise<{ status: number; body: unknown }> {
  // XMLHttpRequest, because fetch can't report upload progress
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/documents`);
    xhr.withCredentials = true;
    const token = getAccessToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // not JSON (the dev server could not reach the API)
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error", "Can't reach the server. Check that the API is running."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** Like uploadDocument, reporting how much of the file was sent (0 to 1). */
export async function uploadDocumentWithProgress(file: File, onProgress: (fraction: number) => void): Promise<Job> {
  let response = await sendUpload(file, onProgress);
  if (response.status === 401) {
    await refreshSession();
    response = await sendUpload(file, onProgress);
  }
  if (response.status >= 200 && response.status < 300) return response.body as Job;
  const error = (response.body as ErrorBody | null)?.error;
  throw new ApiError(response.status, error?.code ?? `http_${response.status}`,
                     error?.message ?? `The upload failed (HTTP ${response.status}).`, error?.request_id ?? null, error?.details);
}

/** The returned job removes the document's vectors, file and record. */
export function deleteDocument(documentId: string): Promise<Job> {
  return request(`/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}
