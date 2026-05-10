// =============================================================================
// PH Agent Hub — Admin ToolList
// =============================================================================
// Ant Design Table/List; type column (erpnext/membrane/custom).
// =============================================================================

import { useState } from "react";
import {
  Table,
  Button,
  Space,
  Tag,
  Popconfirm,
  Switch,
  message,
  Grid,
  List,
  Card,
  Typography,
} from "antd";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTools,
  deleteTool,
  updateTool,
  ToolData,
} from "../../services/admin";
import { ToolForm } from "./ToolForm";

const { useBreakpoint } = Grid;

export function ToolList() {
  const [editingTool, setEditingTool] = useState<ToolData | null>(null);
  const [creating, setCreating] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();

  const { data: tools, isLoading } = useQuery({
    queryKey: ["admin-tools"],
    queryFn: listTools,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTool,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-tools"] });
      message.success("Tool deleted");
    },
  });

  const toggleEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateTool(id, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-tools"] });
    },
  });

  const columns = [
    { title: "Name", dataIndex: "name", key: "name" },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      render: (v: string) => <Tag color="purple">{v}</Tag>,
    },
    {
      title: "Tenant",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 130,
      ellipsis: true,
      responsive: ["lg" as const],
      render: (v: string) => <Typography.Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}…</Typography.Text>,
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      render: (_: boolean, record: ToolData) => (
        <Switch
          checked={record.enabled}
          onChange={(checked) =>
            toggleEnabled.mutate({ id: record.id, enabled: checked })
          }
        />
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: ToolData) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => setEditingTool(record)}
          />
          <Popconfirm
            title="Delete this tool?"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => setCreating(true)}>
          Create Tool
        </Button>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={tools || []}
          renderItem={(tool) => (
            <Card
              size="small"
              style={{ marginBottom: 8 }}
              actions={[
                <Button
                  icon={<EditOutlined />}
                  type="link"
                  onClick={() => setEditingTool(tool)}
                />,
                <Popconfirm
                  title="Delete?"
                  onConfirm={() => deleteMutation.mutate(tool.id)}
                >
                  <Button icon={<DeleteOutlined />} type="link" danger />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={tool.name}
                description={
                  <Space direction="vertical" size={2}>
                    <Tag color="purple">{tool.type}</Tag>
                    <Switch
                      checked={tool.enabled}
                      onChange={(checked) =>
                        toggleEnabled.mutate({
                          id: tool.id,
                          enabled: checked,
                        })
                      }
                      size="small"
                    />
                  </Space>
                }
              />
            </Card>
          )}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={tools || []}
          rowKey="id"
          loading={isLoading}
        />
      )}

      <ToolForm
        open={!!editingTool || creating}
        tool={creating ? null : editingTool}
        onClose={() => {
          setEditingTool(null);
          setCreating(false);
        }}
      />
    </div>
  );
}

export default ToolList;
