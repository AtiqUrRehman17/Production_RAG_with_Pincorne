import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { ALLOWED_EXTENSIONS, deleteDocument, MAX_FILE_SIZE_MB, uploadDocumentWithProgress } from "../../api/documents";
import { getJob, isFinished, listJobs } from "../../api/jobs";
import type { DocumentInfo, Job } from "../../api/types";
import { fileType, plural } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import { toast } from "../../lib/toast";

export type UploadPhase = "uploading" | "queued" | "processing" | "done" | "failed";

export interface UploadItem {
  key: string;
  name: string;
  size: number | null; // unknown for uploads started before this page was opened
  phase: UploadPhase;
  progress: number; // 0-100, while uploading
  jobId?: string;
  message?: string; // the error, or what was ingested
}

const POLL_MS = 1500;

function describeDone(job: Job): string {
  const result = job.result as { pages?: number | null; chunks?: number; already_uploaded?: boolean } | null;
  if (result?.already_uploaded) return "Already in your documents";
  return [result?.pages ? plural(result.pages, "page") : null, result?.chunks != null ? plural(result.chunks, "passage") : null]
    .filter(Boolean).join(" · ") || "Ready";
}

/** Uploads and deletes of documents, followed until their background job is done. */
export function useDocumentJobs() {
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [deleting, setDeleting] = useState<Record<string, string>>({}); // document ID -> delete job ID
  const latest = useRef({ uploads, deleting });
  useEffect(() => {
    latest.current = { uploads, deleting };
  });

  const update = useCallback((key: string, change: Partial<UploadItem>) => {
    setUploads((items) => items.map((item) => (item.key === key ? { ...item, ...change } : item)));
  }, []);

  const refreshDocuments = useCallback(() => void queryClient.invalidateQueries({ queryKey: queryKeys.documents }), [queryClient]);

  // Jobs still running from before this page was opened (e.g. after a reload)
  useEffect(() => {
    let cancelled = false;
    listJobs({ status: ["queued", "processing"], limit: 50 }).then((page) => {
      if (cancelled) return;
      const ingests = page.items.filter((job) => job.type === "ingest");
      setUploads((items) => [
        ...ingests.filter((job) => !items.some((item) => item.jobId === job.id)).map((job): UploadItem => ({
          key: job.id, name: job.file_name ?? "Document", size: null, phase: job.status as UploadPhase, progress: 100, jobId: job.id,
        })),
        ...items,
      ]);
      const deletes = page.items.filter((job) => job.type === "delete" && job.document_id);
      if (deletes.length) setDeleting((map) => ({ ...map, ...Object.fromEntries(deletes.map((job) => [job.document_id!, job.id])) }));
    }, () => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const activeIds = [
    ...uploads.filter((item) => item.jobId && (item.phase === "queued" || item.phase === "processing")).map((item) => item.jobId!),
    ...Object.values(deleting),
  ];
  const activeKey = activeIds.join(",");

  useEffect(() => {
    if (!activeKey) return;
    const ids = activeKey.split(",");
    const timer = setInterval(() => {
      for (const id of ids) {
        getJob(id).then((job) => {
          const upload = latest.current.uploads.find((item) => item.jobId === job.id);
          if (upload && upload.phase !== job.status) {
            const failed = job.status === "failed";
            update(upload.key, { phase: job.status as UploadPhase, message: failed ? job.error ?? "The file could not be processed." : isFinished(job.status) ? describeDone(job) : undefined });
            if (job.status === "done") {
              refreshDocuments();
              toast(`${upload.name} is ready to chat with.`);
            } else if (failed) {
              toast(`${upload.name} could not be processed.`, "error");
            }
          }
          const documentId = Object.keys(latest.current.deleting).find((key) => latest.current.deleting[key] === job.id);
          if (documentId && isFinished(job.status)) {
            setDeleting((map) => {
              const next = { ...map };
              delete next[documentId];
              return next;
            });
            refreshDocuments();
            if (job.status === "done") toast(`${job.file_name ?? "The document"} was deleted.`);
            else toast(job.error ?? "The document could not be deleted.", "error");
          }
        }, () => {});
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [activeKey, update, refreshDocuments]);

  const startUploads = useCallback(async (files: File[]) => {
    const items = files.map((file): [File, UploadItem] => {
      const item: UploadItem = { key: crypto.randomUUID(), name: file.name, size: file.size, phase: "uploading", progress: 0 };
      if (!ALLOWED_EXTENSIONS.includes(fileType(file.name))) {
        Object.assign(item, { phase: "failed", message: "Only PDF, DOCX and TXT files can be uploaded." });
      } else if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        Object.assign(item, { phase: "failed", message: `The file is larger than the ${MAX_FILE_SIZE_MB} MB limit.` });
      } else if (file.size === 0) {
        Object.assign(item, { phase: "failed", message: "The file is empty." });
      }
      return [file, item];
    });
    setUploads((current) => [...items.map(([, item]) => item), ...current]);

    // One after another, so a large batch doesn't hit the server all at once
    for (const [file, item] of items) {
      if (item.phase === "failed") continue;
      try {
        const job = await uploadDocumentWithProgress(file, (fraction) => update(item.key, { progress: Math.round(fraction * 100) }));
        update(item.key, { jobId: job.id, phase: job.status as UploadPhase, progress: 100 });
      } catch (error) {
        update(item.key, { phase: "failed", message: error instanceof ApiError ? error.message : "The upload failed." });
      }
    }
  }, [update]);

  const dismiss = useCallback((key: string) => setUploads((items) => items.filter((item) => item.key !== key)), []);

  const startDelete = useCallback(async (document: DocumentInfo) => {
    const job = await deleteDocument(document.document_id);
    setDeleting((map) => ({ ...map, [document.document_id]: job.id }));
  }, []);

  return { uploads, startUploads, dismiss, deleting, startDelete };
}
