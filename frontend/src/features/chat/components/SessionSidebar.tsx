// =============================================================================
// PH Agent Hub — SessionSidebar
// =============================================================================
// Ant Design Layout.Sider (Drawer on mobile); session list (pinned first);
// new chat button with temp/permanent toggle; links to MemoryManager,
// SessionSearch, logout.
// =============================================================================

import React, { useState } from "react";
import {
  Layout,
  List,
  Button,
  Typography,
  Space,
  Tooltip,
  Drawer,
  Modal,
  Switch,
  Input,
  message,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  PushpinOutlined,
  PushpinFilled,
  DeleteOutlined,
  MenuOutlined,
} from "@ant-design/icons";
import { Logo } from "../../../shared/components/Logo";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../../providers/AuthProvider";
import {
  listSessions,
  createSession,
  deleteSession,
  updateSession,
} from "../services/chat";
import { MemoryManager } from "./MemoryManager";
import { SessionSearch } from "./SessionSearch";

const { Sider } = Layout;
const { Text } = Typography;

export function SessionSidebar() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [newChatModal, setNewChatModal] = useState(false);
  const [newChatTemp, setNewChatTemp] = useState(false);
  const [newChatTitle, setNewChatTitle] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  React.useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const { data: sessions, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createSession({
        title: newChatTitle || "New Chat",
        is_temporary: newChatTemp,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setNewChatModal(false);
      setNewChatTitle("");
      navigate(`/chat/${data.id}`);
    },
    onError: () => message.error("Failed to create session"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      if (sessionId === id) {
        navigate("/chat");
      }
    },
  });

  const pinMutation = useMutation({
    mutationFn: ({ id, is_pinned }: { id: string; is_pinned: boolean }) =>
      updateSession(id, { is_pinned }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  // Sort: pinned first, then by updated_at
  const sortedSessions = [...(sessions || [])].sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1;
    if (!a.is_pinned && b.is_pinned) return 1;
    return (
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  });

  const handleNewChat = () => {
    setNewChatTemp(false);
    setNewChatTitle("");
    setNewChatModal(true);
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const sidebarContent = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#fafafa",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Space
          style={{
            width: "100%",
            justifyContent: "space-between",
          }}
        >
          <Logo size={28} showText textColor="#141414" />
          <Space size={4}>
            <Tooltip title="Search">
              <Button
                type="text"
                icon={<SearchOutlined />}
                size="small"
                onClick={() => setSearchOpen(true)}
              />
            </Tooltip>
            <Tooltip title="Memory">
              <Button
                type="text"
                icon={<DatabaseOutlined />}
                size="small"
                onClick={() => setMemoryOpen(true)}
              />
            </Tooltip>
          </Space>
        </Space>
      </div>

      {/* New Chat Button */}
      <div style={{ padding: "8px 12px" }}>
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          block
          onClick={handleNewChat}
        >
          New Chat
        </Button>
      </div>

      {/* Session List */}
      <div style={{ flex: 1, overflow: "auto" }}>
        <List
          loading={isLoading}
          dataSource={sortedSessions}
          locale={{ emptyText: "No sessions" }}
          renderItem={(item) => (
            <List.Item
              onClick={() => {
                navigate(`/chat/${item.id}`);
                if (isMobile) setMobileOpen(false);
              }}
              style={{
                cursor: "pointer",
                padding: "8px 12px",
                background:
                  sessionId === item.id ? "#e6f4ff" : "transparent",
                borderLeft:
                  sessionId === item.id
                    ? "3px solid #1677ff"
                    : "3px solid transparent",
              }}
              actions={[
                <Tooltip
                  title={item.is_pinned ? "Unpin" : "Pin"}
                  key="pin"
                >
                  <Button
                    type="text"
                    size="small"
                    icon={
                      item.is_pinned ? (
                        <PushpinFilled />
                      ) : (
                        <PushpinOutlined />
                      )
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      pinMutation.mutate({
                        id: item.id,
                        is_pinned: !item.is_pinned,
                      });
                    }}
                  />
                </Tooltip>,
                <Tooltip title="Delete" key="delete">
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteMutation.mutate(item.id);
                    }}
                  />
                </Tooltip>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Text
                    ellipsis
                    style={{
                      maxWidth: collapsed ? 0 : 160,
                      display: "inline-block",
                    }}
                  >
                    {item.is_temporary && "⚡ "}
                    {item.title}
                  </Text>
                }
                description={
                  !collapsed ? (
                    <Text
                      type="secondary"
                      style={{ fontSize: 11 }}
                    >
                      {new Date(item.updated_at).toLocaleDateString()}
                    </Text>
                  ) : null
                }
              />
            </List.Item>
          )}
        />
      </div>

      {/* Footer */}
      <div
        style={{
          padding: "8px 12px",
          borderTop: "1px solid #f0f0f0",
        }}
      >
        <Space
          style={{ width: "100%", justifyContent: "space-between" }}
        >
          <Text type="secondary" style={{ fontSize: 12 }}>
            {user?.display_name}
          </Text>
          <Tooltip title="Logout">
            <Button
              type="text"
              size="small"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
            />
          </Tooltip>
        </Space>
      </div>

      {/* Search Drawer */}
      <Drawer
        title="Search Sessions"
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
      >
        <SessionSearch onClose={() => setSearchOpen(false)} />
      </Drawer>

      {/* Memory Manager */}
      <MemoryManager
        open={memoryOpen}
        onClose={() => setMemoryOpen(false)}
        sessionId={sessionId}
      />

      {/* New Chat Modal */}
      <Modal
        title="New Chat"
        open={newChatModal}
        onOk={() => createMutation.mutate()}
        onCancel={() => setNewChatModal(false)}
        confirmLoading={createMutation.isPending}
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input
            placeholder="Chat title (optional)"
            value={newChatTitle}
            onChange={(e) => setNewChatTitle(e.target.value)}
          />
          <Space>
            <Switch
              checked={newChatTemp}
              onChange={setNewChatTemp}
            />
            <Text>Temporary session (not saved to database)</Text>
          </Space>
        </Space>
      </Modal>
    </div>
  );

  // Mobile: use Drawer
  if (isMobile) {
    return (
      <>
        <Button
          type="text"
          icon={<MenuOutlined />}
          onClick={() => setMobileOpen(true)}
          style={{ position: "fixed", top: 8, left: 8, zIndex: 100 }}
        />
        <Drawer
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          placement="left"
          width={280}
          bodyStyle={{ padding: 0 }}
        >
          {sidebarContent}
        </Drawer>
      </>
    );
  }

  // Desktop: use Sider
  return (
    <Sider
      width={280}
      collapsible
      collapsed={collapsed}
      onCollapse={setCollapsed}
      theme="light"
      style={{
        borderRight: "1px solid #f0f0f0",
        overflow: "auto",
      }}
    >
      {sidebarContent}
    </Sider>
  );
}

export default SessionSidebar;
