import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { streamAnswer } from "../../api/conversations";
import type { ConversationDetail, Message } from "../../api/types";
import { queryKeys } from "../../lib/queryKeys";
import { toast } from "../../lib/toast";

/** The answer being written: shown below the chat's saved messages until it is saved too. */
export interface PendingAnswer {
  conversationId: string;
  question: string;
  questionSaved: boolean; // the question is in the chat's messages now
  text: string;
}

export function useChatStream() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<PendingAnswer | null>(null);
  const controller = useRef<AbortController | null>(null);

  // Leaving the page stops reading the stream; the backend still finishes and saves the answer
  useEffect(() => () => controller.current?.abort(), []);

  const ask = useCallback(async (conversationId: string, question: string) => {
    const abort = new AbortController();
    controller.current = abort;
    const key = queryKeys.conversation(conversationId);
    const append = (message: Message) => queryClient.setQueryData<ConversationDetail>(key, (old) =>
      old && !old.messages.some((m) => m.id === message.id) ? { ...old, messages: [...old.messages, message] } : old);

    setPending({ conversationId, question, questionSaved: false, text: "" });
    try {
      await streamAnswer(conversationId, { question }, {
        onQuestion: (message) => {
          append(message);
          setPending((p) => p && { ...p, questionSaved: true });
        },
        onToken: (text) => setPending((p) => p && { ...p, text: p.text + text }),
        onAnswer: (message) => {
          append(message);
          setPending(null);
        },
        // The failed answer is saved with its error; the refresh below shows it
        onError: () => {},
      }, abort.signal);
    } catch (error) {
      if (abort.signal.aborted) {
        // Stopped: the backend keeps going, so the full answer shows up in the chat a little later
        setTimeout(() => void queryClient.invalidateQueries({ queryKey: key }), 8000);
      } else {
        toast(error instanceof ApiError ? error.message : "The answer could not be loaded.", "error");
      }
    } finally {
      if (controller.current === abort) controller.current = null;
      setPending(null);
      void queryClient.invalidateQueries({ queryKey: key });
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    }
  }, [queryClient]);

  const stop = useCallback(() => {
    controller.current?.abort();
    toast("Stopped. The full answer is still saved to this chat when it's ready.", "info");
  }, []);

  return { pending, ask, stop };
}
