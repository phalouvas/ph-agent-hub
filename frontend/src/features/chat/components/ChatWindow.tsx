// =============================================================================
// PH Agent Hub — ChatWindow
// =============================================================================
// Scrollable message list; streaming token accumulation; stop-generation
// button (calls DELETE /chat/session/:id/stream); uses useStream hook;
// renders MessageBubble list.
// =============================================================================

import React, { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { Button, Input, Space, Spin, Empty, Alert, Switch, Tag, Upload, message, notification } from "antd";
import {
  SendOutlined,
  StopOutlined,
  DownOutlined,
  PaperClipOutlined,
  CompressOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageBubble } from "./MessageBubble";
import { useStream } from "../hooks/useStream";
import {
  listMessages,
  deleteMessage,
  regenerateMessage,
  summarizeSession,
} from "../services/chat";
import api from "../../../services/api";
import {
  ModelSelector,
  TemplateSelector,
  SkillSelector,
  PromptLibrary,
  TemporaryChatBadge,
  SessionToolActivation,
} from "./";

const { TextArea } = Input;

// ---------------------------------------------------------------------------
// Pending file info (stored after upload completes)
// ---------------------------------------------------------------------------

interface PendingFile {
  file_id: string;
  original_filename: string;
}

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
  const [followUpQuestions, setFollowUpQuestions] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const [toolsOpen, setToolsOpen] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [uploading, setUploading] = useState(false);

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
    setFollowUpQuestions([]);

    // Re-enable auto-scroll when user sends a new message
    userScrolledUpRef.current = false;
    setShowScrollButton(false);

    // Optimistic: show the user message immediately
    setPendingUserMessage({
      id: `pending-user-${Date.now()}`,
      content,
    });

    const fileIds = pendingFiles.map((f) => f.file_id);
    setPendingFiles([]);

    startStream(sessionId, content, fileIds.length > 0 ? fileIds : undefined, {
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
      onFollowUpQuestions(questions) {
        setFollowUpQuestions(questions);
      },
      onSummarized(data) {
        notification.info({
          message: "Conversation Summarized",
          description: `Compressed ${data.summarized_message_count} earlier messages to save context space.`,
          placement: "topRight",
          duration: 4,
        });
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
        // Don't clear followUpQuestions here — they are set after
        // message_complete and should persist until the next message.
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

  // File upload handlers
  const handleFileUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await api<{
          file_id: string;
          original_filename: string;
        }>(`/chat/session/${sessionId}/upload`, {
          method: "POST",
          body: formData,
        });
        setPendingFiles((prev) => [
          ...prev,
          {
            file_id: res.file_id,
            original_filename: res.original_filename,
          },
        ]);
        message.success(`${file.name} attached`);
      } catch {
        message.error(`Failed to upload ${file.name}`);
      } finally {
        setUploading(false);
      }
      return false; // Prevent default Upload behavior
    },
    [sessionId],
  );

  const handleRemoveFile = useCallback((fileId: string) => {
    setPendingFiles((prev) => prev.filter((f) => f.file_id !== fileId));
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Build a flat display list: real messages + optimistic user message + streaming bubble
  const displayMessages: Array<any> = [...(messages || [])];

  // Show the user's message immediately at the bottom (optimistic UI)
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
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      onDrop={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const files = Array.from(e.dataTransfer.files);
        for (const file of files) {
          await handleFileUpload(file);
        }
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
        <Button
          size="small"
          onClick={() => setToolsOpen(true)}
        >
          Tools
        </Button>
        <Button
          size="small"
          icon={<CompressOutlined />}
          onClick={async () => {
            try {
              const result = await summarizeSession(sessionId);
              notification.success({
                message: "Conversation Summarized",
                description: `Compressed ${result.summarized_message_count} messages. Saved ~${result.tokens_saved} tokens.`,
                placement: "topRight",
                duration: 5,
              });
              queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
            } catch (err: any) {
              message.error(err?.message || "Summarization failed");
            }
          }}
          title="Summarize conversation"
        >
          Summarize
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
                !isTemporary
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

        {/* Follow-up questions chips */}
        {!streaming && followUpQuestions.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              padding: "0 0 12px 0",
              justifyContent: "flex-start",
            }}
          >
            {followUpQuestions.map((q, i) => (
              <Button
                key={i}
                size="small"
                type="default"
                style={{
                  borderRadius: 16,
                  maxWidth: "100%",
                  whiteSpace: "normal",
                  height: "auto",
                  padding: "4px 12px",
                  textAlign: "left",
                }}
                onClick={() => {
                  setInputValue(q);
                  setFollowUpQuestions([]);
                  // Auto-send on next tick after state settles
                  setTimeout(() => {
                    const textarea = document.querySelector(
                      `[data-session-id="${sessionId}"] textarea, #chat-input-${sessionId}`
                    ) as HTMLTextAreaElement;
                    if (textarea) {
                      textarea.focus();
                    }
                  }, 0);
                }}
              >
                {q}
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Input area */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid #f0f0f0",
        }}
      >
        {/* Pending file chips */}
        {pendingFiles.length > 0 && (
          <div style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
            {pendingFiles.map((f) => (
              <Tag
                key={f.file_id}
                closable
                onClose={() => handleRemoveFile(f.file_id)}
                color="blue"
              >
                {f.original_filename}
              </Tag>
            ))}
          </div>
        )}

        <Space.Compact style={{ width: "100%" }}>
          <Upload
            multiple
            showUploadList={false}
            beforeUpload={async (file) => {
              await handleFileUpload(file);
              return false;
            }}
            disabled={streaming || isTemporary}
            accept={
              ".pdf,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.gif,.webp," +
              "application/pdf,text/csv,text/plain,text/markdown," +
              "application/json,image/png,image/jpeg,image/gif,image/webp"
            }
          >
            <Button
              icon={<PaperClipOutlined />}
              disabled={streaming || isTemporary}
              loading={uploading}
              title="Attach files"
            />
          </Upload>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isTemporary
                ? "Type a message... (temporary session)"
                : "Type a message... (Enter to send, Shift+Enter for new line)"
            }
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
