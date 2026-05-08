// =============================================================================
// PH Agent Hub — ChatWindow
// =============================================================================
// Scrollable message list; streaming token accumulation; stop-generation
// button (calls DELETE /chat/session/:id/stream); uses useStream hook;
// renders MessageBubble list.
// =============================================================================

import React, { useRef, useEffect, useState, useCallback } from "react";
import { Button, Input, Space, Spin, Empty, Alert, Switch } from "antd";
import {
  SendOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageBubble } from "./MessageBubble";
import { useStream } from "../hooks/useStream";
import {
  listMessages,
  deleteMessage,
  regenerateMessage,
} from "../services/chat";
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

  const { streaming, startStream, stopStream } = useStream();

  const { data: messages, isLoading: loadingMessages } = useQuery({
    queryKey: ["messages", sessionId],
    queryFn: () => listMessages(sessionId),
    refetchInterval: false,
  });

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent, toolEvents]);

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || streaming) return;
    const content = inputValue.trim();
    setInputValue("");
    setStreamingContent("");
    setStreamingReasoningContent("");
    setStreamError(null);
    setToolEvents([]);

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
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      },
      onError(err) {
        setStreamError(err);
        console.error("Stream error:", err);
      },
      onClose() {
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

  // Build a flat display list: real messages + streaming bubble
  const displayMessages = [...(messages || [])];
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
          style={{ opacity: thinkingEnabled != null ? 0.6 : 1 }}
        />
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflow: "auto",
          padding: "16px",
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
