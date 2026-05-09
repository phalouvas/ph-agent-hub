// =============================================================================
// PH Agent Hub — Admin MemoryList
// =============================================================================
// Ant Design Table; list + delete all memory entries (admin/manager scoped).
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
  listAdminMemories,
  deleteAdminMemory,
  MemoryData,
} from "../../services/admin";

const { useBreakpoint } = Grid;
const { Text, Paragraph } = Typography;

export function MemoryList() {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();
  const [searchText, setSearchText] = useState("");

  const { data: memories, isLoading } = useQuery({
    queryKey: ["admin-memories"],
    queryFn: () => listAdminMemories(),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAdminMemory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-memories"] });
      message.success("Memory entry deleted");
    },
  });

  const filteredData = (memories || []).filter((m) => {
    if (!searchText.trim()) return true;
    const lower = searchText.toLowerCase();
    return (
      m.key.toLowerCase().includes(lower) ||
      m.value.toLowerCase().includes(lower) ||
      m.user_id.toLowerCase().includes(lower) ||
      m.source.toLowerCase().includes(lower)
    );
  });

  const columns = [
    {
      title: "Key",
      dataIndex: "key",
      key: "key",
      render: (v: string, record: MemoryData) => (
        <Space>
          <Text strong>{v}</Text>
          <Tag color={record.source === "automatic" ? "blue" : "green"}>
            {record.source}
          </Tag>
        </Space>
      ),
    },
    {
      title: "Value",
      dataIndex: "value",
      key: "value",
      ellipsis: true,
      render: (v: string) => (
        <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, maxWidth: 300 }}>
          {v}
        </Paragraph>
      ),
    },
    {
      title: "Tenant",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 120,
      ellipsis: true,
      responsive: ["lg" as const],
    },
    {
      title: "User",
      dataIndex: "user_id",
      key: "user_id",
      width: 120,
      ellipsis: true,
      responsive: ["lg" as const],
    },
    {
      title: "Session",
      dataIndex: "session_id",
      key: "session_id",
      width: 120,
      ellipsis: true,
      responsive: ["xl" as const],
      render: (v: string | null) =>
        v ? <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}…</Text> : <Text type="secondary">—</Text>,
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
      render: (_: unknown, record: MemoryData) => (
        <Popconfirm
          title="Delete this memory entry?"
          onConfirm={() => deleteMutation.mutate(record.id)}
        >
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>
      ),
    },
  ];

  const mobileRender = (item: MemoryData) => (
    <Card
      size="small"
      style={{ marginBottom: 8 }}
      actions={[
        <Popconfirm
          key="del"
          title="Delete this memory entry?"
          onConfirm={() => deleteMutation.mutate(item.id)}
        >
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>,
      ]}
    >
      <Card.Meta
        title={
          <Space>
            <Text strong>{item.key}</Text>
            <Tag color={item.source === "automatic" ? "blue" : "green"}>
              {item.source}
            </Tag>
          </Space>
        }
        description={
          <>
            <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0 }}>
              {item.value}
            </Paragraph>
            <Text type="secondary" style={{ fontSize: 11 }}>
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
          placeholder="Search by key, value, user, source…"
          prefix={<SearchOutlined />}
          allowClear
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 320 }}
        />
        <Text type="secondary">
          {filteredData.length} of {memories?.length || 0} entries
        </Text>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={filteredData}
          locale={{ emptyText: "No memory entries found" }}
          renderItem={mobileRender}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="id"
          loading={isLoading}
          size="middle"
          pagination={{ pageSize: 20, showSizeChanger: true }}
        />
      )}
    </div>
  );
}

export default MemoryList;