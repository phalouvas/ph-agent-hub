// =============================================================================
// PH Agent Hub — ChatWindow
// =============================================================================
// Scrollable message list; streaming token accumulation; stop-generation
// button (calls DELETE /chat/session/:id/stream); uses useStream hook;
// renders MessageBubble list.
// =============================================================================

import React, { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { Button, Input, Space, Spin, Empty, Alert, Switch } from "antd";
import {
  SendOutlined,
  StopOutlined,
  DownOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageBubble } from "./MessageBubble";
import { useStream } from "../hooks/useStream";
import {
  listMessages,
  deleteMessage,
  regenerateMessage,
} from "../services/chat";
import api from "../../../services/api";
import {
  ModelSelector,
  TemplateSelector,
  SkillSelector,
  PromptLibrary,
  FileUpload,
  TemporaryChatBadge,
  SessionToolActivation,
} from "./";

const { TextArea } = Input;

interface ChatWindowProps {
  sessionId: string;
  isTemporary?: boolean;
  selectedModelId?: string;
  selectedTemplateId?: string;
  selectedSkillId?: string;
  selectedPromptId?: string;
  onSessionUpdate?: (data: Record<string, unknown>) => void;
}

export function ChatWindow({
  sessionId,
  isTemporary,
  selectedModelId,
  selectedTemplateId,
  selectedSkillId,
  selectedPromptId,
  onSessionUpdate,
}: ChatWindowProps) {
  const [inputValue, setInputValue] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingReasoningContent, setStreamingReasoningContent] = useState("");
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [thinkingEnabled, setThinkingEnabled] = useState<boolean | null>(null);
  const [toolEvents, setToolEvents] = useState<Array<{type: string; data: Record<string, unknown>}>>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const [toolsOpen, setToolsOpen] = useState(false);

  // Track whether the user has manually scrolled up (to disable auto-scroll)
  const userScrolledUpRef = useRef(false);
  // State for showing the "scroll to bottom" button (refs don't trigger re-renders)
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Optimistic user message — shown immediately on send, replaced by
  // the real persisted message when the response completes or the
  // stream is stopped / errors out.
  const [pendingUserMessage, setPendingUserMessage] = useState<{
    id: string;
    content: string;
  } | null>(null);

  const { streaming, startStream, stopStream } = useStream();

  const { data: messages, isLoading: loadingMessages } = useQuery({
    queryKey: ["messages", sessionId],
    queryFn: () => listMessages(sessionId),
    refetchInterval: false,
  });

  // Fetch models to determine if selected model supports thinking
  interface ModelInfo {
    id: string;
    thinking_enabled: boolean;
    provider: string;
  }
  const { data: modelList } = useQuery({
    queryKey: ["models"],
    queryFn: () => api<ModelInfo[]>("/models"),
  });
  const selectedModel = useMemo(
    () => (modelList || []).find((m) => m.id === selectedModelId),
    [modelList, selectedModelId],
  );
  const modelSupportsThinking = selectedModel?.thinking_enabled === true;

  // Smart auto-scroll: only scroll to bottom when user hasn't scrolled up.
  // Allows the user to interrupt auto-scroll by scrolling up, and resumes
  // auto-scroll when they scroll back to the bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || userScrolledUpRef.current) return;
    // Use requestAnimationFrame to avoid layout thrashing during rapid token updates
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [messages, streamingContent, toolEvents]);

  // Scroll event handler: detect when user manually scrolls away from the bottom
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Threshold in pixels — user is "at bottom" if within 80px of the bottom edge
    const threshold = 80;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const scrolledUp = distanceFromBottom > threshold;
    userScrolledUpRef.current = scrolledUp;
    setShowScrollButton(scrolledUp);
  }, []);

  // Scroll to bottom and re-enable auto-scroll
  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    userScrolledUpRef.current = false;
    setShowScrollButton(false);
  }, []);

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || streaming) return;
    const content = inputValue.trim();
    setInputValue("");
    setStreamingContent("");
    setStreamingReasoningContent("");
    setStreamError(null);
    setToolEvents([]);

    // Re-enable auto-scroll when user sends a new message
    userScrolledUpRef.current = false;
    setShowScrollButton(false);

    // Optimistic: show the user message immediately
    setPendingUserMessage({
      id: `pending-user-${Date.now()}`,
      content,
    });

    startStream(sessionId, content, undefined, {
      onToken(token, msgId) {
        setStreamingMessageId(msgId);
        setStreamingContent((prev) => prev + token);
      },
      onReasoningToken(delta) {
        setStreamingReasoningContent((prev) => prev + delta);
      },
      onToolStart(data) {
        setToolEvents((prev) => [
          ...prev,
          { type: "function_call", data },
        ]);
      },
      onToolResult(data) {
        setToolEvents((prev) => [
          ...prev,
          { type: "function_result", data },
        ]);
      },
      onMessageComplete() {
        setPendingUserMessage(null);
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      },
      onError(err) {
        setPendingUserMessage(null);
        setStreamError(err);
        console.error("Stream error:", err);
      },
      onClose() {
        setPendingUserMessage(null);
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      },
    });
  }, [inputValue, streaming, sessionId, startStream, queryClient]);

  const handleStop = async () => {
    await stopStream(sessionId);
  };

  const handleEdit = async (messageId: string) => {
    // Reload model to start edit flow — simple approach: prompt user
    const msg = (messages || []).find((m) => m.id === messageId);
    if (msg) {
      const text = parseTextFromContent(msg.content);
      setInputValue(text);
    }
  };

  const handleDelete = async (messageId: string) => {
    await deleteMessage(sessionId, messageId);
    queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
  };

  const handleRegenerate = async (messageId: string) => {
    await regenerateMessage(sessionId, messageId);
    queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Build a flat display list: optimistic user message + real messages + streaming bubble
  const displayMessages: Array<any> = [];

  // 1. Show the user's message immediately (optimistic UI)
  if (pendingUserMessage) {
    displayMessages.push({
      id: pendingUserMessage.id,
      session_id: sessionId,
      parent_message_id: null,
      branch_index: 0,
      sender: "user" as const,
      content: [{ type: "text", text: pendingUserMessage.content }],
      model_id: null,
      tool_calls: null,
      is_deleted: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }

  // 2. Real persisted messages from the backend
  displayMessages.push(...(messages || []));
  if (streamingContent && streamingMessageId) {
    displayMessages.push({
      id: streamingMessageId,
      session_id: sessionId,
      parent_message_id: null,
      branch_index: 0,
      sender: "assistant" as const,
      content: [
        ...(streamingReasoningContent
          ? [{ type: "reasoning", text: streamingReasoningContent }]
          : []),
        ...(streamingContent
          ? [{ type: "text", text: streamingContent }]
          : []),
        ...toolEvents.map((ev) => ({
          type: ev.type,
          name: (ev.data as Record<string, unknown>).tool_name,
          arguments: (ev.data as Record<string, unknown>).arguments,
          output: (ev.data as Record<string, unknown>).result_summary,
          is_error: !(ev.data as Record<string, unknown>).success,
          call_id: (ev.data as Record<string, unknown>).tool_call_id,
        })),
      ],
      model_id: selectedModelId || null,
      tool_calls: null,
      is_deleted: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#fff",
      }}
    >
      {/* Top bar */}
      <div
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid #f0f0f0",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        {isTemporary !== undefined && (
          <TemporaryChatBadge isTemporary={isTemporary} />
        )}
        <ModelSelector
          value={selectedModelId}
          onChange={(id) => onSessionUpdate?.({ selected_model_id: id })}
        />
        <TemplateSelector
          value={selectedTemplateId}
          onChange={(id) => onSessionUpdate?.({ selected_template_id: id })}
        />
        <SkillSelector
          value={selectedSkillId}
          onChange={(id) => onSessionUpdate?.({ selected_skill_id: id })}
        />
        <PromptLibrary
          selectedPromptId={selectedPromptId}
          onSelect={(id) => onSessionUpdate?.({ selected_prompt_id: id })}
        />
        <FileUpload
          sessionId={sessionId}
          disabled={isTemporary}
        />
        <Button
          size="small"
          onClick={() => setToolsOpen(true)}
        >
          Tools
        </Button>
        {modelSupportsThinking && (
          <Switch
            size="small"
            checked={thinkingEnabled ?? true}
            checkedChildren="🧠"
            unCheckedChildren="🧠"
            title="Thinking Mode"
            onChange={(v) => {
              setThinkingEnabled(v);
              onSessionUpdate?.({ thinking_enabled: v });
            }}
          />
        )}
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{
          flex: 1,
          overflow: "auto",
          padding: "16px",
          position: "relative",
        }}
      >
        {streamError && (
          <Alert
            message="Error"
            description={streamError}
            type="error"
            closable
            onClose={() => setStreamError(null)}
            style={{ marginBottom: 12 }}
          />
        )}
        {loadingMessages ? (
          <div style={{ textAlign: "center", padding: 48 }}>
            <Spin />
          </div>
        ) : displayMessages.length === 0 ? (
          <Empty
            description="No messages yet. Start a conversation!"
            style={{ marginTop: 64 }}
          />
        ) : (
          displayMessages.map((msg) => (
            <MessageBubble
              key={msg.id + (msg.id === streamingMessageId ? "-streaming" : "")}
              message={msg}
              sessionId={sessionId}
              onEdit={msg.sender === "user" ? handleEdit : undefined}
              onDelete={
                msg.sender === "user" && !isTemporary
                  ? handleDelete
                  : undefined
              }
              onRegenerate={
                msg.sender === "assistant" && !isTemporary
                  ? handleRegenerate
                  : undefined
              }
              disabled={streaming}
            />
          ))
        )}

        {/* Scroll-to-bottom floating button — appears when user scrolls up */}
        {showScrollButton && (
          <Button
            shape="circle"
            size="small"
            icon={<DownOutlined />}
            onClick={scrollToBottom}
            style={{
              position: "sticky",
              bottom: 16,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 10,
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            }}
            title="Scroll to bottom"
          />
        )}
      </div>

      {/* Input area */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid #f0f0f0",
        }}
      >
        <Space.Compact style={{ width: "100%" }}>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
            autoSize={{ minRows: 1, maxRows: 6 }}
            disabled={streaming}
            style={{ resize: "none" }}
          />
          {streaming ? (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={handleStop}
            >
              Stop
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputValue.trim()}
            >
              Send
            </Button>
          )}
        </Space.Compact>
      </div>

      {/* Tools drawer */}
      <SessionToolActivation
        sessionId={sessionId}
        open={toolsOpen}
        onClose={() => setToolsOpen(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function parseTextFromContent(content: unknown): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter((c) => c && typeof c === "object" && c.type === "text")
      .map((c) => c.text || "")
      .join("");
  }
  return "";
}

export default ChatWindow;
