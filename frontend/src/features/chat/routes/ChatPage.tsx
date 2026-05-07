// =============================================================================
// PH Agent Hub — ChatPage
// =============================================================================
// Main chat layout: SessionSidebar + ChatWindow + input area.
// =============================================================================

import { useParams, useNavigate } from "react-router-dom";
import { Layout, Empty, Button, Typography, Spin } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { SessionSidebar } from "../components/SessionSidebar";
import { ChatWindow } from "../components/ChatWindow";
import { getSession, createSession } from "../services/chat";

const { Content } = Layout;
const { Title, Text } = Typography;

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data: session, isLoading: loadingSession } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
  });

  const handleSessionUpdate = (_data: Record<string, unknown>) => {
    // This would call updateSession, but for simplicity in the ChatWindow
    // we just pass this handler through
  };

  const handleNewChat = async () => {
    try {
      const session = await createSession({ title: "New Chat" });
      navigate(`/chat/${session.id}`);
    } catch {
      // Error creating session
    }
  };

  return (
    <Layout style={{ height: "100vh" }}>
      <SessionSidebar />
      <Content>
        {!sessionId ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              height: "100%",
              gap: 16,
            }}
          >
            <Title level={3} style={{ margin: 0 }}>
              Welcome to PH Agent Hub
            </Title>
            <Text type="secondary">
              Select a conversation from the sidebar or start a new one
            </Text>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              size="large"
              onClick={handleNewChat}
            >
              New Chat
            </Button>
          </div>
        ) : loadingSession ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "100%",
            }}
          >
            <Spin size="large" />
          </div>
        ) : session ? (
          <ChatWindow
            sessionId={session.id}
            isTemporary={session.is_temporary}
            selectedModelId={session.selected_model_id ?? undefined}
            selectedTemplateId={session.selected_template_id ?? undefined}
            selectedSkillId={session.selected_skill_id ?? undefined}
            selectedPromptId={session.selected_prompt_id ?? undefined}
            onSessionUpdate={handleSessionUpdate}
          />
        ) : (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "100%",
            }}
          >
            <Empty description="Session not found" />
          </div>
        )}
      </Content>
    </Layout>
  );
}

export default ChatPage;
