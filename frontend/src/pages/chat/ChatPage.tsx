import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router";

import { ApiError } from "../../api/client";
import { createConversation, deleteConversation, getConversation, updateConversation } from "../../api/conversations";
import type { Conversation, ConversationDetail } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { ErrorMessage } from "../../components/ErrorMessage";
import { FullPageSpinner } from "../../components/FullPageSpinner";
import { Icon } from "../../components/Icon";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { button, cx, field, iconButton } from "../../components/ui";
import { queryKeys } from "../../lib/queryKeys";
import { toast } from "../../lib/toast";
import { useDocuments } from "../../lib/useDocuments";
import { Composer } from "./Composer";
import { ConversationSidebar } from "./ConversationSidebar";
import { EmptyChat } from "./EmptyChat";
import { AssistantMessage, PendingMessage, UserMessage } from "./Messages";
import { ScopePicker } from "./ScopePicker";
import { useChatStream } from "./useChatStream";

export function ChatPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { documents } = useDocuments();
  const stream = useChatStream();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dialog, setDialog] = useState<"rename" | "delete" | null>(null);
  const [creating, setCreating] = useState(false);
  // For a new chat: which documents it will use ("Chat with this document" passes one)
  const [newScope, setNewScope] = useState<string[] | null>(
    () => (location.state as { documentIds?: string[] } | null)?.documentIds ?? null);

  const conversation = useQuery({
    queryKey: queryKeys.conversation(conversationId ?? ""),
    queryFn: () => getConversation(conversationId!),
    enabled: !!conversationId,
  });
  const chat = conversationId ? conversation.data : undefined;
  const pending = stream.pending?.conversationId === conversationId ? stream.pending : null;
  const scope = chat ? chat.document_ids : newScope;
  const scopedDocuments = scope ? documents.filter((d) => scope.includes(d.document_id)) : documents;

  // Follow the answer as it is written, unless the user scrolled up to read
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const messageCount = chat?.messages.length ?? 0;
  useLayoutEffect(() => {
    stickToBottom.current = true;
  }, [conversationId]);
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [conversationId, messageCount, pending?.text, pending?.questionSaved, conversation.isSuccess]);

  function newChat() {
    setNewScope(null);
    setDrawerOpen(false);
    navigate("/chat");
  }

  async function send(question: string) {
    let id = conversationId;
    if (!id) {
      setCreating(true);
      try {
        const created = await createConversation({ document_ids: newScope });
        queryClient.setQueryData<ConversationDetail>(queryKeys.conversation(created.id), { ...created, messages: [] });
        void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
        id = created.id;
        navigate(`/chat/${created.id}`);
      } catch (error) {
        toast(error instanceof ApiError ? error.message : "The chat could not be started.", "error");
        return;
      } finally {
        setCreating(false);
      }
    }
    stickToBottom.current = true;
    void stream.ask(id, question);
  }

  function saveConversation(updated: Conversation) {
    queryClient.setQueryData<ConversationDetail>(queryKeys.conversation(updated.id), (old) => old && { ...old, ...updated });
    void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
  }

  async function changeScope(documentIds: string[] | null) {
    if (!chat) {
      setNewScope(documentIds);
      return;
    }
    try {
      saveConversation(await updateConversation(chat.id, { document_ids: documentIds }));
    } catch (error) {
      toast(error instanceof Error ? error.message : "The documents could not be changed.", "error");
    }
  }

  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = String(new FormData(event.currentTarget).get("title")).trim();
    if (!chat || !title) return;
    try {
      saveConversation(await updateConversation(chat.id, { title }));
      setDialog(null);
      toast("Chat renamed.");
    } catch (error) {
      toast(error instanceof Error ? error.message : "The chat could not be renamed.", "error");
    }
  }

  async function remove() {
    if (!chat) return;
    await deleteConversation(chat.id);
    queryClient.removeQueries({ queryKey: queryKeys.conversation(chat.id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    toast("Chat deleted.");
    navigate("/chat");
  }

  const passageCount = documents.reduce((sum, d) => sum + d.chunk_count, 0);
  const sidebarProps = { onNewChat: newChat, documentCount: documents.length, passageCount };

  let content;
  if (conversationId && conversation.isPending) {
    content = <FullPageSpinner />;
  } else if (conversationId && conversation.isError) {
    const missing = conversation.error instanceof ApiError && conversation.error.status === 404;
    content = (
      <div className="grid h-full place-items-center px-4 text-center">
        <div className="max-w-sm space-y-4">
          {missing ? <p className="text-sm text-zinc-500 dark:text-zinc-400">This chat doesn't exist, or it was deleted.</p>
                   : <ErrorMessage error={conversation.error} />}
          <button type="button" onClick={newChat} className={button("primary")}><Icon name="plus" className="size-4" /> New chat</button>
        </div>
      </div>
    );
  } else if (chat && (chat.messages.length || pending)) {
    content = (
      <div className="mx-auto max-w-3xl space-y-7 px-4 py-6 sm:px-6 sm:py-8">
        {chat.messages.map((message, i) => message.role === "user"
          ? <UserMessage key={message.id} content={message.content} />
          : <AssistantMessage key={message.id} message={message} conversationId={chat.id} isAdmin={user?.role === "admin"}
                              onRetry={!pending && chat.messages[i - 1]?.role === "user"
                                ? () => send(chat.messages[i - 1].content) : undefined} />)}
        {pending && !pending.questionSaved && <UserMessage content={pending.question} />}
        {pending && <PendingMessage pending={pending} />}
      </div>
    );
  } else {
    content = <EmptyChat documents={scopedDocuments} onAsk={send} />;
  }

  return (
    <div className="flex h-full min-h-0">
      <ConversationSidebar {...sidebarProps} />
      {drawerOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="absolute inset-0 bg-zinc-950/40 backdrop-blur-[2px]" onClick={() => setDrawerOpen(false)} />
          <div className="relative"><ConversationSidebar {...sidebarProps} mobile onClose={() => setDrawerOpen(false)} /></div>
        </div>
      )}

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-1.5 border-b border-zinc-200 px-2 sm:px-4 dark:border-zinc-800">
          <button type="button" onClick={() => setDrawerOpen(true)} className={cx(iconButton, "size-9 lg:hidden")} aria-label="Chats">
            <Icon name="menu" />
          </button>
          <h1 className="min-w-0 truncate pl-1 font-semibold">{chat ? chat.title || "New chat" : "New chat"}</h1>
          {chat && (
            <button type="button" onClick={() => setDialog("rename")} className={iconButton} title="Rename"><Icon name="pencil" className="size-4" /></button>
          )}
          <div className="ml-auto flex shrink-0 items-center gap-1">
            <ScopePicker documents={documents} selected={scope ?? null} onChange={changeScope} />
            {chat && (
              <button type="button" onClick={() => setDialog("delete")} className={cx(iconButton, "size-9 hover:text-rose-600!")} title="Delete chat">
                <Icon name="trash" className="size-4" />
              </button>
            )}
          </div>
        </header>

        <div ref={scroller} className="scroll-thin flex-1 overflow-y-auto"
             onScroll={(event) => {
               const el = event.currentTarget;
               stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
             }}>
          {content}
        </div>

        <Composer key={conversationId ?? "new"} streaming={!!pending} disabled={creating || !!stream.pending}
                  onSend={send} onStop={stream.stop} />
      </section>

      {dialog === "rename" && chat && (
        <Modal onClose={() => setDialog(null)} label="Rename chat">
          <h2 className="font-semibold">Rename chat</h2>
          <form onSubmit={rename} className="mt-4">
            <input name="title" defaultValue={chat.title} maxLength={200} required className={field} aria-label="Chat name" />
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button type="button" onClick={() => setDialog(null)} className={button("secondary")}>Cancel</button>
              <button type="submit" className={button("primary")}>Save</button>
            </div>
          </form>
        </Modal>
      )}
      {dialog === "delete" && chat && (
        <ConfirmDialog title="Delete this chat?" confirmLabel="Delete chat" onConfirm={remove} onClose={() => setDialog(null)}
                       text="The chat and all its messages are deleted. Your documents are not affected." />
      )}
    </div>
  );
}
