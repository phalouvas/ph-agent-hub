// =============================================================================
// PH Agent Hub — ChatWindow
// =============================================================================
// Scrollable message list; streaming token accumulation; stop-generation
// button (calls DELETE /chat/session/:id/stream); uses useStream hook;
// renders MessageBubble list.
// =============================================================================

import React, { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { Button, Input, Space, Spin, Empty, Alert, Switch, Tag, Typography, Upload, message, notification } from "antd";
import {
  SendOutlined,
  StopOutlined,
  DownOutlined,
  PaperClipOutlined,
  CompressOutlined,
  RobotOutlined,
  EditOutlined,
  CloseOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageBubble } from "./MessageBubble";
import { useStream } from "../hooks/useStream";
import {
  listMessages,
  editMessage,
  deleteMessage,
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
const { Text } = Typography;

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
  const [streamingTokens, setStreamingTokens] = useState<{ tokens_in: number; tokens_out: number } | null>(null);
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

  const [editingMsgId, setEditingMsgId] = useState<string | null>(null);
  const [editingLoading, setEditingLoading] = useState(false);
  const [regeneratingMsgId, setRegeneratingMsgId] = useState<string | null>(null);

  // Branch state: map of parent_message_id -> active branch_index
  const [activeBranches, setActiveBranches] = useState<Record<string, number>>({});

  const { streaming, startStream, startRegenerateStream, stopStream } = useStream();

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
  }, [messages, streamingContent, toolEvents, streaming]);

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
    setStreamingTokens(null);

    // Re-enable auto-scroll when user sends a new message
    userScrolledUpRef.current = false;
    setShowScrollButton(false);

    // ---- Edit mode: call branching edit API ----
    if (editingMsgId) {
      const msgId = editingMsgId;
      setEditingMsgId(null);
      setEditingLoading(true);

      // Optimistic: show the edited user message immediately
      setPendingUserMessage({
        id: `pending-edit-${Date.now()}`,
        content,
      });

      try {
        // Call the backend branching edit API
        await editMessage(sessionId, msgId, content);
        setPendingUserMessage(null);
        setEditingLoading(false);
        // Auto-switch to the new branch (highest branch_index) after edit.
        // Only works when the edited message has a non-null parent.
        const originalMsg = (messages || []).find((m) => m.id === msgId);
        if (originalMsg?.parent_message_id) {
          const parentKey = originalMsg.parent_message_id;
          setActiveBranches((prev) => {
            const siblings = (messages || []).filter(
              (m) => m.parent_message_id === parentKey,
            );
            const maxBranch = Math.max(...siblings.map((s) => s.branch_index ?? 0), 0) + 1;
            return { ...prev, [parentKey]: maxBranch };
          });
        }
        queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      } catch (err: any) {
        setPendingUserMessage(null);
        setEditingLoading(false);
        setStreamError(err?.message || "Edit failed");
        message.error(err?.message || "Failed to edit message");
      }
      return;
    }

    // ---- Normal send mode ----
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
      onMessageComplete(data) {
        setPendingUserMessage(null);
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        if (data.tokens_in || data.tokens_out) {
          setStreamingTokens({ tokens_in: data.tokens_in || 0, tokens_out: data.tokens_out || 0 });
        }
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
        setStreamingTokens(null);
        setStreamError(err);
        console.error("Stream error:", err);
      },
      onClose() {
        setPendingUserMessage(null);
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        setStreamingTokens(null);
        // Don't clear followUpQuestions here — they are set after
        // message_complete and should persist until the next message.
        queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      },
    });
  }, [inputValue, streaming, sessionId, startStream, queryClient, pendingFiles, editingMsgId]);

  const handleStop = async () => {
    await stopStream(sessionId);
  };

  const handleEdit = useCallback((messageId: string) => {
    const msg = (messages || []).find((m) => m.id === messageId);
    if (msg) {
      const text = parseTextFromContent(msg.content);
      setInputValue(text);
      setEditingMsgId(messageId);
    }
  }, [messages]);

  const handleCancelEdit = useCallback(() => {
    setEditingMsgId(null);
    setInputValue("");
  }, []);

  const handleDelete = async (messageId: string) => {
    await deleteMessage(sessionId, messageId);
    queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
  };

  const handleRegenerate = useCallback((messageId: string) => {
    if (streaming) return;
    setRegeneratingMsgId(messageId);
    setStreamingContent("");
    setStreamingReasoningContent("");
    setStreamError(null);
    setToolEvents([]);
    setFollowUpQuestions([]);
    setStreamingTokens(null);

    // Re-enable auto-scroll
    userScrolledUpRef.current = false;
    setShowScrollButton(false);

    startRegenerateStream(sessionId, messageId, {
      onToken(token, msgId) {
        setStreamingMessageId(msgId);
        setStreamingContent((prev) => prev + token);
      },
      onReasoningToken(delta) {
        setStreamingReasoningContent((prev) => prev + delta);
      },
      onToolStart(data) {
        setToolEvents((prev) => [...prev, { type: "function_call", data }]);
      },
      onToolResult(data) {
        setToolEvents((prev) => [...prev, { type: "function_result", data }]);
      },
      onMessageComplete(data) {
        setRegeneratingMsgId(null);
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        if (data.tokens_in || data.tokens_out) {
          setStreamingTokens({ tokens_in: data.tokens_in || 0, tokens_out: data.tokens_out || 0 });
        }
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
        setRegeneratingMsgId(null);
        setStreamingTokens(null);
        setStreamError(err);
        message.error(err || "Regenerate failed");
      },
      onClose() {
        setRegeneratingMsgId(null);
        setStreamingContent("");
        setStreamingReasoningContent("");
        setStreamingMessageId(null);
        setToolEvents([]);
        setStreamingTokens(null);
        queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      },
    });
  }, [streaming, sessionId, startRegenerateStream, queryClient]);

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

  // ---- Branch tree: compute which messages have siblings ----
  // Only compute for messages with non-null parents.  Root-level
  // messages (parent_message_id=NULL) can mix sequential messages and
  // edited branches; without explicit tracking of which was edited we
  // cannot reliably tell them apart.  Child-level branching (regenerate)
  // is unambiguous — all children of a parent are always branches.
  const branchTree = useMemo(() => {
    const byParent: Record<string, Set<number>> = {};
    for (const m of messages || []) {
      const parent = m.parent_message_id;
      if (!parent) continue;
      if (!byParent[parent]) byParent[parent] = new Set();
      byParent[parent].add(m.branch_index ?? 0);
    }
    const tree: Record<string, { currentIndex: number; totalBranches: number }> = {};
    for (const m of messages || []) {
      const parent = m.parent_message_id;
      if (!parent || !byParent[parent]) continue;
      const siblings = byParent[parent];
      if (siblings.size > 1) {
        tree[m.id] = {
          currentIndex: m.branch_index ?? 0,
          totalBranches: siblings.size,
        };
      }
    }
    return tree;
  }, [messages]);

  // ---- Branch-aware message list ----
  // Filter out messages from inactive branches, then flatten
  const displayMessages: Array<any> = useMemo(() => {
    const msgs = (messages || []).filter(
      (m) => m.id !== regeneratingMsgId,
    );

    // Build a set of message IDs that should be hidden (not on active branch)
    const hiddenIds = new Set<string>();

    for (const m of msgs) {
      const parent = m.parent_message_id;
      if (!parent) continue;

      // Check if this parent has multiple branches
      const allSiblings = msgs.filter(
        (s) => s.parent_message_id === parent,
      );
      const branchIndices = [...new Set(allSiblings.map((s) => s.branch_index ?? 0))];

      if (branchIndices.length > 1) {
        const activeIdx = activeBranches[parent] ?? 0;
        if ((m.branch_index ?? 0) !== activeIdx) {
          hiddenIds.add(m.id);
          // Also hide children of hidden messages recursively
          const hideDescendants = (pid: string) => {
            for (const child of msgs) {
              if (child.parent_message_id === pid) {
                hiddenIds.add(child.id);
                hideDescendants(child.id);
              }
            }
          };
          hideDescendants(m.id);
        }
      }
    }

    // Build ordered display list, hiding inactive branches
    const ordered: any[] = [];
    const seen = new Set<string>();

    // Walk the tree depth-first to preserve parent-child ordering
    const walk = (msg: any) => {
      if (!msg || seen.has(msg.id) || hiddenIds.has(msg.id)) return;
      seen.add(msg.id);
      ordered.push(msg);
      // Find children ordered by branch_index, then created_at
      const children = msgs
        .filter((c) => c.parent_message_id === msg.id && !hiddenIds.has(c.id))
        .sort((a, b) => (a.branch_index ?? 0) - (b.branch_index ?? 0) ||
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      for (const child of children) {
        walk(child);
      }
    };

    // Start with root messages (parent_message_id is null)
    const roots = msgs
      .filter((m) => !m.parent_message_id && !hiddenIds.has(m.id))
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    for (const root of roots) {
      walk(root);
    }

    // Add optimistic user message if present
    if (pendingUserMessage) {
      ordered.push({
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
    // Add streaming bubble if present
    if (streamingContent && streamingMessageId) {
      ordered.push({
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
        tokens_in: streamingTokens?.tokens_in ?? null,
        tokens_out: streamingTokens?.tokens_out ?? null,
        is_deleted: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    }
    return ordered;
  }, [messages, regeneratingMsgId, pendingUserMessage, streamingContent, streamingMessageId,
      streamingReasoningContent, toolEvents, streamingTokens, selectedModelId, sessionId,
      activeBranches]);

  // ---- Branch navigation callback ----
  const handleNavigateBranch = useCallback((messageId: string, branchIndex: number) => {
    const msg = (messages || []).find((m) => m.id === messageId);
    if (msg && msg.parent_message_id) {
      setActiveBranches((prev) => ({ ...prev, [msg.parent_message_id!]: branchIndex }));
    }
  }, [messages]);

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
      <style>{`
        @keyframes thinkingDot {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
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
              branchInfo={branchTree[msg.id] ?? null}
              onNavigateBranch={(idx) => handleNavigateBranch(msg.id, idx)}
              disabled={streaming || editingLoading}
              regenerating={regeneratingMsgId === msg.id}
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

        {/* Thinking placeholder — shown while streaming but before first token */}
        {streaming && !streamingContent && !streamingMessageId && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 4 }}>
              <Space style={{ marginLeft: 4 }}>
                <RobotOutlined style={{ color: "#52c41a" }} />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Assistant
                </Text>
              </Space>
            </div>
            <div
              style={{
                display: "inline-block",
                maxWidth: "80%",
                padding: "12px 16px",
                borderRadius: 12,
                borderBottomLeftRadius: 4,
                background: "#f0f0f0",
              }}
            >
              <Space size={4}>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    style={{
                      display: "inline-block",
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: "#bbb",
                      animation: `thinkingDot 1.4s ease-in-out ${i * 0.2}s infinite`,
                    }}
                  />
                ))}
                <Text type="secondary" style={{ fontSize: 13, marginLeft: 4 }}>
                  AI is thinking…
                </Text>
              </Space>
            </div>
          </div>
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

        {/* Edit mode indicator */}
        {editingMsgId && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 8,
              padding: "4px 12px",
              background: "#fff7e6",
              border: "1px solid #ffd591",
              borderRadius: 6,
            }}
          >
            <EditOutlined style={{ color: "#fa8c16" }} />
            <Text type="secondary" style={{ fontSize: 13, flex: 1 }}>
              Editing message — a new branch will be created
            </Text>
            <Button
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={handleCancelEdit}
            />
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
            disabled={streaming || isTemporary || !!editingMsgId}
            accept={
              ".pdf,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.gif,.webp," +
              "application/pdf,text/csv,text/plain,text/markdown," +
              "application/json,image/png,image/jpeg,image/gif,image/webp"
            }
          >
            <Button
              icon={<PaperClipOutlined />}
              disabled={streaming || isTemporary || !!editingMsgId}
              loading={uploading}
              title="Attach files"
            />
          </Upload>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              editingMsgId
                ? "Edit your message... (Enter to send)"
                : isTemporary
                ? "Type a message... (temporary session)"
                : "Type a message... (Enter to send, Shift+Enter for new line)"
            }
            autoSize={{ minRows: 1, maxRows: 6 }}
            disabled={streaming || editingLoading}
            style={{ resize: "none" }}
          />
          {streaming || editingLoading ? (
            <Space size={4}>
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
                  loading
                  disabled
                >
                  Sending…
                </Button>
              )}
              <Spin size="small" />
            </Space>
          ) : (
            <Button
              type="primary"
              icon={editingMsgId ? <EditOutlined /> : <SendOutlined />}
              onClick={handleSend}
              disabled={!inputValue.trim()}
            >
              {editingMsgId ? "Edit & Send" : "Send"}
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
