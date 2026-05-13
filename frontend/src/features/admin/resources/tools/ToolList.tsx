// =============================================================================
// PH Agent Hub — Admin ToolList
// =============================================================================
// Ant Design Table/List; type column (erpnext/membrane/custom).
// =============================================================================

import { useState, useMemo } from "react";
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
  Select,
} from "antd";
import { EditOutlined, DeleteOutlined, CopyOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTools,
  deleteTool,
  updateTool,
  listTenants,
  ToolData,
} from "../../services/admin";
import { ToolForm } from "./ToolForm";

const { useBreakpoint } = Grid;

export function ToolList() {
  const [editingTool, setEditingTool] = useState<ToolData | null>(null);
  const [duplicatingTool, setDuplicatingTool] = useState<ToolData | null>(null);
  const [creating, setCreating] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get("tenant_id") || undefined;

  const { data: tools, isLoading } = useQuery({
    queryKey: ["admin-tools", tenantId],
    queryFn: () => listTools({ tenant_id: tenantId }),
  });

  const { data: tenants } = useQuery({
    queryKey: ["admin-tenants-tool-list"],
    queryFn: () => listTenants(),
  });

  const tenantNameById = new Map((tenants || []).map((t) => [t.id, t.name]));

  const CATEGORY_LABELS: Record<string, string> = {
    financial: "Financial",
    web: "Web",
    enterprise: "Enterprise",
    utility: "Utility",
    custom: "Custom",
    system: "System",
    general: "General",
  };

  const CATEGORY_COLORS: Record<string, string> = {
    financial: "green",
    web: "blue",
    enterprise: "orange",
    utility: "cyan",
    custom: "purple",
    system: "default",
    general: "default",
  };

  const filteredTools = useMemo(() => {
    if (!tools) return [];
    if (!categoryFilter) return tools;
    return tools.filter((t) => t.category === categoryFilter);
  }, [tools, categoryFilter]);

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
      title: "Category",
      dataIndex: "category",
      key: "category",
      render: (v: string) => (
        <Tag color={CATEGORY_COLORS[v] || "default"}>
          {CATEGORY_LABELS[v] || v}
        </Tag>
      ),
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      render: (v: string, record: ToolData) => (
        <Space size={4}>
          <Tag color="purple">{v}</Tag>
          {v === "custom" && record.code && (
            <Tag color="green" style={{ fontSize: 11 }}>code</Tag>
          )}
        </Space>
      ),
    },
    {
      title: "Tenant",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 130,
      ellipsis: true,
      responsive: ["lg" as const],
      render: (v: string) => {
        const tenantName = tenantNameById.get(v);
        return tenantName ? (
          <Typography.Text>{tenantName}</Typography.Text>
        ) : (
          <Typography.Text type="secondary">Unknown tenant</Typography.Text>
        );
      },
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
          <Button
            icon={<CopyOutlined />}
            size="small"
            onClick={() => setDuplicatingTool(record)}
            title="Duplicate"
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

      <Space style={{ marginBottom: 16, marginLeft: 8 }}>
        <Select
          allowClear
          placeholder="Filter by category"
          style={{ width: 180 }}
          value={categoryFilter}
          onChange={(val) => setCategoryFilter(val)}
          options={Object.entries(CATEGORY_LABELS).map(([value, label]) => ({
            label,
            value,
          }))}
        />
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={filteredTools}
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
                <Button
                  icon={<CopyOutlined />}
                  type="link"
                  onClick={() => setDuplicatingTool(tool)}
                  title="Duplicate"
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
                    <Space size={4}>
                      <Tag color={CATEGORY_COLORS[tool.category] || "default"}>
                        {CATEGORY_LABELS[tool.category] || tool.category}
                      </Tag>
                      <Tag color="purple">{tool.type}</Tag>
                      {tool.type === "custom" && tool.code && (
                        <Tag color="green" style={{ fontSize: 11 }}>code</Tag>
                      )}
                    </Space>
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
          dataSource={filteredTools}
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

      <ToolForm
        open={!!duplicatingTool}
        tool={null}
        duplicateFrom={duplicatingTool}
        onClose={() => setDuplicatingTool(null)}
      />
    </div>
  );
}

export default ToolList;
