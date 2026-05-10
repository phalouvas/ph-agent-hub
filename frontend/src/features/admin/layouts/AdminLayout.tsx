// =============================================================================
// PH Agent Hub — AdminLayout
// =============================================================================
// Ant Design Layout with fixed Sider on desktop, Drawer on mobile (<768px);
// sidebar nav items; hides Tenants+Settings menu items for manager role;
// role badge in top bar.
// =============================================================================

import { useState } from "react";
import { Layout, Menu, Button, Typography, Space, Tag, Drawer, Grid } from "antd";
import {
  UserOutlined,
  TeamOutlined,
  ApiOutlined,
  ToolOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  SettingOutlined,
  LogoutOutlined,
  MenuOutlined,
  GroupOutlined,
  DatabaseOutlined,
  CommentOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useAuth } from "../../../providers/AuthProvider";
import { Logo } from "../../../shared/components/Logo";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;
const { useBreakpoint } = Grid;

export function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isAdmin = user?.role === "admin";

  const menuItems = [
    { key: "/admin/users", icon: <UserOutlined />, label: "Users" },
    ...(isAdmin
      ? [{ key: "/admin/tenants", icon: <TeamOutlined />, label: "Tenants" }]
      : []),
    { key: "/admin/models", icon: <ApiOutlined />, label: "Models" },
    { key: "/admin/tools", icon: <ToolOutlined />, label: "Tools" },
    {
      key: "/admin/templates",
      icon: <FileTextOutlined />,
      label: "Templates",
    },
    {
      key: "/admin/skills",
      icon: <ThunderboltOutlined />,
      label: "Skills",
    },
    {
      key: "/admin/groups",
      icon: <GroupOutlined />,
      label: "Groups",
    },
    {
      key: "/admin/memories",
      icon: <DatabaseOutlined />,
      label: "Memories",
    },
    {
      key: "/admin/sessions",
      icon: <CommentOutlined />,
      label: "Sessions",
    },
    {
      key: "/admin/analytics",
      icon: <BarChartOutlined />,
      label: "Analytics",
    },
    ...(isAdmin
      ? [
          {
            key: "/admin/settings",
            icon: <SettingOutlined />,
            label: "Settings",
          },
        ]
      : []),
  ];

  const selectedKey = menuItems.find((item) =>
    location.pathname.startsWith(item.key),
  )?.key;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const sidebarContent = (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          padding: "16px",
          textAlign: "center",
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <Logo size={30} showText textColor="#fff" />
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={selectedKey ? [selectedKey] : []}
        items={menuItems}
        onClick={({ key }) => {
          navigate(key);
          setMobileMenuOpen(false);
        }}
        style={{ flex: 1 }}
      />
      <div style={{ padding: "8px 16px", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
        <Button
          type="text"
          icon={<LogoutOutlined />}
          onClick={handleLogout}
          style={{ color: "rgba(255,255,255,0.65)", width: "100%", textAlign: "left" }}
        >
          Logout
        </Button>
      </div>
    </div>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {isMobile ? (
        <>
          <Header
            style={{
              background: "#001529",
              padding: "0 16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Button
              type="text"
              icon={<MenuOutlined style={{ color: "#fff" }} />}
              onClick={() => setMobileMenuOpen(true)}
            />
            <Space>
              <Button
                type="text"
                icon={<MessageOutlined style={{ color: "#fff" }} />}
                onClick={() => navigate("/chat")}
              />
              <Tag color={isAdmin ? "red" : "blue"}>
                {user?.role}
              </Tag>
              <Text style={{ color: "#fff" }}>{user?.display_name}</Text>
            </Space>
          </Header>
          <Drawer
            open={mobileMenuOpen}
            onClose={() => setMobileMenuOpen(false)}
            placement="left"
            width={260}
            bodyStyle={{ padding: 0, background: "#001529" }}
          >
            {sidebarContent}
          </Drawer>
        </>
      ) : (
        <Sider width={240} theme="dark">
          {sidebarContent}
        </Sider>
      )}

      <Layout>
        {!isMobile && (
          <Header
            style={{
              background: "#fff",
              padding: "0 24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              borderBottom: "1px solid #f0f0f0",
            }}
          >
            <Space>
              <Button
                size="small"
                onClick={() => navigate("/chat")}
              >
                Back to Chat
              </Button>
              <Tag color={isAdmin ? "red" : "blue"}>
                {user?.role}
              </Tag>
              <Text>{user?.display_name}</Text>
            </Space>
          </Header>
        )}
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

export default AdminLayout;
