// =============================================================================
// PH Agent Hub — useStream Hook
// =============================================================================
// fetchEventSource wrapper; handles token/tool_start/tool_result/
// step_complete/message_complete/error/heartbeat events per
// streaming-protocol.md §5.
// POST to /chat/session/:id/message with Accept: text/event-stream.
// =============================================================================

import { useState, useCallback, useRef } from "react";
import {
  fetchEventSource,
  EventStreamContentType,
} from "@microsoft/fetch-event-source";
import { getToken } from "../../../services/api";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TokenEvent {
  event: "token";
  data: {
    session_id: string;
    message_id: string;
    delta: string;
    step_name?: string;
  };
}

export interface ToolStartEvent {
  event: "tool_start";
  data: {
    session_id: string;
    message_id: string;
    tool_name: string;
    tool_call_id: string;
    arguments: Record<string, unknown>;
  };
}

export interface ToolResultEvent {
  event: "tool_result";
  data: {
    session_id: string;
    message_id: string;
    tool_call_id: string;
    tool_name: string;
    success: boolean;
    result_summary: unknown;
  };
}

export interface StepCompleteEvent {
  event: "step_complete";
  data: {
    session_id: string;
    message_id: string;
    step_name: string;
  };
}

export interface MessageCompleteEvent {
  event: "message_complete";
  data: {
    session_id: string;
    message_id: string;
    content: string;
    model_id: string;
  };
}

export interface ReasoningTokenEvent {
  event: "reasoning_token";
  data: {
    session_id: string;
    message_id: string;
    delta: string;
  };
}

export interface ErrorEvent {
  event: "error";
  data: {
    session_id: string;
    message_id: string;
    error: string;
  };
}

export interface HeartbeatEvent {
  event: "heartbeat";
  data: Record<string, never>;
}

export type StreamEvent =
  | TokenEvent
  | ToolStartEvent
  | ToolResultEvent
  | StepCompleteEvent
  | MessageCompleteEvent
  | ReasoningTokenEvent
  | ErrorEvent
  | HeartbeatEvent;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useStream() {
  const [streaming, setStreaming] = useState(false);
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(
    null,
  );
  const abortRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (
      sessionId: string,
      content: string,
      fileIds: string[] | undefined,
      handlers: {
        onToken?: (token: string, messageId: string) => void;
        onToolStart?: (data: ToolStartEvent["data"]) => void;
        onToolResult?: (data: ToolResultEvent["data"]) => void;
        onStepComplete?: (data: StepCompleteEvent["data"]) => void;
        onMessageComplete?: (data: MessageCompleteEvent["data"]) => void;
        onReasoningToken?: (delta: string, messageId: string) => void;
        onError?: (error: string, messageId: string) => void;
        onClose?: () => void;
      },
    ) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      setStreamingSessionId(sessionId);

      const token = getToken();

      try {
        await fetchEventSource(
          `${BASE_URL}/chat/session/${sessionId}/message`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "text/event-stream",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({
              content,
              file_ids: fileIds || [],
            }),
            signal: controller.signal,
            async onopen(response) {
              if (
                response.ok &&
                response.headers
                  .get("content-type")
                  ?.includes(EventStreamContentType)
              ) {
                return;
              }
              throw new Error(
                `Stream failed with status ${response.status}`,
              );
            },
            onmessage(ev) {
              try {
                const parsed = JSON.parse(ev.data);
                switch (ev.event) {
                  case "token":
                    handlers.onToken?.(parsed.delta, parsed.message_id);
                    break;
                  case "tool_start":
                    handlers.onToolStart?.(parsed);
                    break;
                  case "tool_result":
                    handlers.onToolResult?.(parsed);
                    break;
                  case "step_complete":
                    handlers.onStepComplete?.(parsed);
                    break;
                  case "message_complete":
                    handlers.onMessageComplete?.(parsed);
                    break;
                  case "reasoning_token":
                    handlers.onReasoningToken?.(parsed.delta, parsed.message_id);
                    break;
                  case "error":
                    handlers.onError?.(parsed.message || parsed.error || "Unknown error", parsed.message_id);
                    break;
                  case "heartbeat":
                    // Ignore heartbeats
                    break;
                }
              } catch {
                // Ignore parse errors on individual events
              }
            },
            onclose() {
              setStreaming(false);
              setStreamingSessionId(null);
              handlers.onClose?.();
            },
            onerror(err) {
              // Don't throw on abort
              if (controller.signal.aborted) {
                setStreaming(false);
                setStreamingSessionId(null);
                return; // stops the retry
              }
              // Don't throw — let onclose fire to clean up state and refresh messages
              setStreaming(false);
              setStreamingSessionId(null);
              handlers.onClose?.();
              throw err; // rethrow to stop retries but onclose already ran
            },
          },
        );
      } catch (err) {
        if (!controller.signal.aborted) {
          handlers.onError?.(String(err), "");
        }
        setStreaming(false);
        setStreamingSessionId(null);
      }
    },
    [],
  );

  const stopStream = useCallback(
    async (sessionId: string) => {
      abortRef.current?.abort();
      // Also call backend cancel
      try {
        const token = getToken();
        await fetch(`${BASE_URL}/chat/session/${sessionId}/stream`, {
          method: "DELETE",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } catch {
        // Best effort
      }
      setStreaming(false);
      setStreamingSessionId(null);
    },
    [],
  );

  return {
    streaming,
    streamingSessionId,
    startStream,
    stopStream,
  };
}

export default useStream;
