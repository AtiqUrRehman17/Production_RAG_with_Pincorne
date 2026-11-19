import { useState } from "react";
import { useNavigate } from "react-router";

import type { DocumentInfo } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Icon } from "../../components/Icon";
import { ConfirmDialog } from "../../components/Modal";
import { EmptyState, PageHeader, Tabs } from "../../components/PageHeader";
import { button, card, cx } from "../../components/ui";
import { formatBytes, plural } from "../../lib/format";
import { useDocuments } from "../../lib/useDocuments";
import { DocumentList } from "./DocumentList";
import { SearchPassages } from "./SearchPassages";
import { ACCEPT, DropZone, UploadList } from "./UploadArea";
import { useDocumentJobs } from "./useDocumentJobs";

type Tab = "library" | "search";

export function DocumentsPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("library");
  const [toDelete, setToDelete] = useState<DocumentInfo | null>(null);
  const query = useDocuments();
  const { documents } = query;
  const jobs = useDocumentJobs();

  const passages = documents.reduce((sum, d) => sum + d.chunk_count, 0);
  const totalBytes = documents.reduce((sum, d) => sum + d.size_bytes, 0);

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">
        <PageHeader
          title="Documents & Knowledge Base"
          subtitle={
            query.isSuccess
              ? `${plural(documents.length, "document")} indexed · ${plural(passages, "passage")} vectorized in Pinecone`
              : "Manage your private vector store"
          }
          actions={
            <label className={cx(button("primary"), "cursor-pointer shadow-sm shadow-blue-600/20")}>
              <Icon name="upload" className="size-4" /> Upload Files
              <input
                type="file"
                multiple
                accept={ACCEPT}
                className="sr-only"
                onChange={(event) => {
                  void jobs.startUploads([...(event.target.files ?? [])]);
                  event.target.value = "";
                }}
              />
            </label>
          }
        />

        {/* Knowledge Base Metrics Strip */}
        {query.isSuccess && (
          <div className="my-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className={cx(card, "p-4")}>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Documents</p>
              <p className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                {documents.length}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">PDF, DOCX, TXT</p>
            </div>
            <div className={cx(card, "p-4")}>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Vector Passages</p>
              <p className="mt-1 text-2xl font-bold tracking-tight text-blue-600 dark:text-blue-400">
                {passages.toLocaleString()}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">800-token chunks</p>
            </div>
            <div className={cx(card, "p-4")}>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Storage Used</p>
              <p className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                {formatBytes(totalBytes)}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">Local upload cache</p>
            </div>
            <div className={cx(card, "p-4")}>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Vector Index</p>
              <div className="mt-1.5 flex items-center gap-1.5 text-sm font-bold text-emerald-600 dark:text-emerald-400">
                <span className="relative flex size-2">
                  <span className="pulse-radar absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
                </span>
                <span>Active & Synced</span>
              </div>
              <p className="mt-0.5 text-[11px] text-slate-400">Pinecone (768d)</p>
            </div>
          </div>
        )}

        <Tabs<Tab>
          items={[
            { key: "library", label: "Library", count: query.isSuccess ? documents.length : undefined },
            { key: "search", label: "Diagnostic Search" },
          ]}
          active={tab}
          onChange={setTab}
        />

        {tab === "library" ? (
          <div className="mt-6 space-y-6">
            <DropZone onFiles={(files) => void jobs.startUploads(files)} />
            <UploadList items={jobs.uploads} onDismiss={jobs.dismiss} />
            {query.isPending && (
              <div className={cx(card, "space-y-3 p-4")}>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="shimmer h-12 rounded-lg" />
                ))}
              </div>
            )}
            {query.isError && <ErrorMessage error={query.error} />}
            {query.isSuccess &&
              (documents.length ? (
                <DocumentList
                  documents={documents}
                  deleting={jobs.deleting}
                  onDelete={setToDelete}
                  onChat={(d) => navigate("/chat", { state: { documentIds: [d.document_id] } })}
                />
              ) : (
                <EmptyState
                  title="No documents yet"
                  text="Upload your first document above to enable grounded AI answering."
                />
              ))}
            {query.hasNextPage && (
              <button
                type="button"
                onClick={() => void query.fetchNextPage()}
                disabled={query.isFetchingNextPage}
                className={cx(button("secondary"), "w-full text-xs font-medium")}
              >
                {query.isFetchingNextPage ? "Loading…" : "Show more documents"}
              </button>
            )}
          </div>
        ) : (
          <SearchPassages hasDocuments={documents.length > 0} />
        )}
      </div>

      {toDelete && (
        <ConfirmDialog
          title={`Delete ${toDelete.file_name}?`}
          confirmLabel="Delete document"
          text="Its vector embeddings will be pruned from Pinecone, and future chats will not be able to cite it. Previous chat answers will preserve their historical text."
          onConfirm={() => jobs.startDelete(toDelete)}
          onClose={() => setToDelete(null)}
        />
      )}
    </div>
  );
}
