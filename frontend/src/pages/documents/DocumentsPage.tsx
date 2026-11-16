import { useState } from "react";
import { useNavigate } from "react-router";

import type { DocumentInfo } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Icon } from "../../components/Icon";
import { ConfirmDialog } from "../../components/Modal";
import { EmptyState, PageHeader, Tabs } from "../../components/PageHeader";
import { button, card, cx } from "../../components/ui";
import { plural } from "../../lib/format";
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

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">
        <PageHeader title="Documents"
                    subtitle={query.isSuccess ? `${plural(documents.length, "document")} · ${plural(passages, "passage")} ready to search` : " "}
                    actions={(
                      <label className={cx(button("primary"), "cursor-pointer")}>
                        <Icon name="upload" className="size-4" /> Upload
                        <input type="file" multiple accept={ACCEPT} className="sr-only"
                               onChange={(event) => { void jobs.startUploads([...(event.target.files ?? [])]); event.target.value = ""; }} />
                      </label>
                    )} />
        <Tabs<Tab> items={[{ key: "library", label: "Library", count: query.isSuccess ? documents.length : undefined },
                           { key: "search", label: "Search passages" }]}
                   active={tab} onChange={setTab} />

        {tab === "library" ? (
          <div className="mt-6 space-y-6">
            <DropZone onFiles={(files) => void jobs.startUploads(files)} />
            <UploadList items={jobs.uploads} onDismiss={jobs.dismiss} />
            {query.isPending && (
              <div className={cx(card, "space-y-3 p-4")}>{[1, 2, 3].map((i) => <div key={i} className="shimmer h-10 rounded-lg" />)}</div>
            )}
            {query.isError && <ErrorMessage error={query.error} />}
            {query.isSuccess && (documents.length ? (
              <DocumentList documents={documents} deleting={jobs.deleting} onDelete={setToDelete}
                            onChat={(d) => navigate("/chat", { state: { documentIds: [d.document_id] } })} />
            ) : <EmptyState title="No documents yet" text="Upload a file above to start chatting with it." />)}
            {query.hasNextPage && (
              <button type="button" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage} className={cx(button("secondary"), "w-full")}>
                {query.isFetchingNextPage ? "Loading…" : "Show more documents"}
              </button>
            )}
          </div>
        ) : <SearchPassages hasDocuments={documents.length > 0} />}
      </div>

      {toDelete && (
        <ConfirmDialog title={`Delete ${toDelete.file_name}?`} confirmLabel="Delete document"
                       text="Its passages are removed from search, and chats can no longer cite it. Past answers keep their text."
                       onConfirm={() => jobs.startDelete(toDelete)} onClose={() => setToDelete(null)} />
      )}
    </div>
  );
}
