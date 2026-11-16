import { request } from "./client";
import type { Feedback, FeedbackIn } from "./types";

const path = (messageId: string) => `/messages/${encodeURIComponent(messageId)}/feedback`;

/** Give or change the rating of an answer (also sent to LangSmith in the background). */
export function setFeedback(messageId: string, body: FeedbackIn): Promise<Feedback> {
  return request(path(messageId), { body });
}

export function removeFeedback(messageId: string): Promise<void> {
  return request(path(messageId), { method: "DELETE" });
}
