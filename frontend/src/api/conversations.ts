import { ApiError, apiFetch, request } from "./client";
import type {
  AskRequest, AskResponse, Conversation, ConversationCreate, ConversationDetail,
  ConversationUpdate, ErrorBody, Message, Page, PageParams,
} from "./types";

const path = (id: string) => `/conversations/${encodeURIComponent(id)}`;

export function listConversations(params: PageParams = {}): Promise<Page<Conversation>> {
  return request("/conversations", { query: { ...params } });
}

export function createConversation(body: ConversationCreate = {}): Promise<Conversation> {
  return request("/conversations", { body });
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return request(path(id));
}

export function updateConversation(id: string, body: ConversationUpdate): Promise<Conversation> {
  return request(path(id), { method: "PATCH", body });
}

export function deleteConversation(id: string): Promise<void> {
  return request(path(id), { method: "DELETE" });
}

/** The whole answer at once. */
export function ask(id: string, body: AskRequest): Promise<AskResponse> {
  return request(`${path(id)}/messages`, { body });
}

export interface StreamHandlers {
  onQuestion?: (message: Message) => void; // the question was saved
  onToken?: (text: string) => void; // the next piece of the answer
  onAnswer?: (message: Message) => void; // the finished answer, with citations
  onError?: (error: ApiError) => void; // the answer failed after the stream started
}

/**
 * The answer word by word (Server-Sent Events over a POST, so fetch instead of EventSource).
 * Errors before the stream starts (wrong chat ID, not logged in) are thrown; errors after
 * it started go to onError. The backend keeps going and saves the answer even if this is aborted.
 */
export async function streamAnswer(id: string, body: AskRequest, handlers: StreamHandlers,
                                   signal?: AbortSignal): Promise<void> {
  const response = await apiFetch(`${path(id)}/messages/stream`, { body, signal });
  if (!response.body) throw new ApiError(0, "stream_unsupported", "This browser can't read streamed answers.");

  const dispatch = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (data.length === 0) return;
    const payload: unknown = JSON.parse(data.join("\n"));
    if (event === "question") handlers.onQuestion?.(payload as Message);
    else if (event === "token") handlers.onToken?.((payload as { text: string }).text);
    else if (event === "answer") handlers.onAnswer?.(payload as Message);
    else if (event === "error") {
      const error = (payload as ErrorBody).error;
      handlers.onError?.(new ApiError(500, error.code, error.message, error.request_id, error.details));
    }
  };

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer = (buffer + value).replace(/\r\n/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      dispatch(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
    }
  }
  if (buffer.trim()) dispatch(buffer);
}
