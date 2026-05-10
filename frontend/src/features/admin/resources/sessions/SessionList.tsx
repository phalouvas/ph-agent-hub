// =============================================================================
// PH Agent Hub — Admin SessionList
// =============================================================================
// Ant Design Table; list + delete sessions (admin/manager scoped).
// =============================================================================

import { useState } from "react";
import {
  Table,
  Button,
  Tag,
  Popconfirm,
  Input,
  Space,
  message,
  Grid,
  List,
  Card,
  Typography,
} from "antd";
import {
  DeleteOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAdminSessions,
  deleteAdminSession,
  AdminSessionData,
} from "../../services/admin";

const { useBreakpoint } = Grid;
const { Text } = Typography;

export function SessionList() {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();
  const [searchText, setSearchText] = useState("");

  const { data: sessions, isLoading } = useQuery({
    queryKey: ["admin-sessions"],
    queryFn: () => listAdminSessions(),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAdminSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      message.success("Session deleted");
    },
  });

  const filteredData = (sessions || []).filter((s) => {
    if (!searchText.trim()) return true;
    const lower = searchText.toLowerCase();
    const tagNames = (s.tags || []).map((t) => t.name.toLowerCase()).join(" ");
    return (
      s.title.toLowerCase().includes(lower) ||
      s.user_id.toLowerCase().includes(lower) ||
      s.tenant_id.toLowerCase().includes(lower) ||
      tagNames.includes(lower)
    );
  });

  const columns = [
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      render: (v: string, record: AdminSessionData) => (
        <Space>
          <Text strong>{v}</Text>
          {record.is_pinned && <Tag color="orange">Pinned</Tag>}
          {record.is_temporary && <Tag color="blue">Temp</Tag>}
        </Space>
      ),
    },
    {
      title: "Tags",
      dataIndex: "tags",
      key: "tags",
      render: (tags: AdminSessionData["tags"]) => (
        <Space size={4} wrap>
          {(tags || []).slice(0, 5).map((t) => (
            <Tag key={t.id} color={t.color || "default"} style={{ fontSize: 11 }}>
              {t.name}
            </Tag>
          ))}
          {(tags || []).length > 5 && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              +{tags.length - 5} more
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: "Tenant",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 120,
      ellipsis: true,
      responsive: ["lg" as const],
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}…</Text>,
    },
    {
      title: "User",
      dataIndex: "user_id",
      key: "user_id",
      width: 120,
      ellipsis: true,
      responsive: ["lg" as const],
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}…</Text>,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 120,
      responsive: ["md" as const],
      render: (v: string) => new Date(v).toLocaleDateString(),
    },
    {
      title: "Actions",
      key: "actions",
      width: 80,
      render: (_: unknown, record: AdminSessionData) => (
        <Popconfirm
          title="Delete this session?"
          onConfirm={() => deleteMutation.mutate(record.id)}
        >
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>
      ),
    },
  ];

  const mobileRender = (item: AdminSessionData) => (
    <Card
      size="small"
      style={{ marginBottom: 8 }}
      actions={[
        <Popconfirm
          key="del"
          title="Delete this session?"
          onConfirm={() => deleteMutation.mutate(item.id)}
        >
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>,
      ]}
    >
      <Card.Meta
        title={
          <Space>
            <Text strong>{item.title}</Text>
            {item.is_pinned && <Tag color="orange">Pinned</Tag>}
          </Space>
        }
        description={
          <>
            <Space size={4} wrap style={{ marginBottom: 4 }}>
              {(item.tags || []).map((t) => (
                <Tag key={t.id} color={t.color || "default"} style={{ fontSize: 10 }}>
                  {t.name}
                </Tag>
              ))}
            </Space>
            <Text type="secondary" style={{ fontSize: 11, display: "block" }}>
              User: {item.user_id.slice(0, 8)}… ·{" "}
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </>
        }
      />
    </Card>
  );

  return (
    <div>
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <Input
          placeholder="Search by title, tags, user, tenant…"
          prefix={<SearchOutlined />}
          allowClear
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 320 }}
        />
        <Text type="secondary">
          {filteredData.length} of {sessions?.length || 0} sessions
        </Text>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={filteredData}
          locale={{ emptyText: "No sessions found" }}
          renderItem={mobileRender}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={filteredData}
          loading={isLoading}
          locale={{ emptyText: "No sessions found" }}
          pagination={{ pageSize: 50, showSizeChanger: true }}
        />
      )}
    </div>
  );
}

export default SessionList;
