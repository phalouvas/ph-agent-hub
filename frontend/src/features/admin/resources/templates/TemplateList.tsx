// =============================================================================
// PH Agent Hub — Admin TemplateList
// =============================================================================
// Ant Design Table/List.
// =============================================================================

import { useState } from "react";
import {
  Table,
  Button,
  Space,
  Tag,
  Popconfirm,
  message,
  Grid,
  List,
  Card,
} from "antd";
import { EditOutlined, DeleteOutlined, CopyOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTemplates,
  deleteTemplate,
  TemplateData,
} from "../../services/admin";
import { TemplateForm } from "./TemplateForm";

const { useBreakpoint } = Grid;

export function TemplateList() {
  const [editingTemplate, setEditingTemplate] = useState<TemplateData | null>(null);
  const [duplicatingTemplate, setDuplicatingTemplate] = useState<TemplateData | null>(null);
  const [creating, setCreating] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get("tenant_id") || undefined;

  const { data: templates, isLoading } = useQuery({
    queryKey: ["admin-templates", tenantId],
    queryFn: () => listTemplates({ tenant_id: tenantId }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-templates"] });
      message.success("Template deleted");
    },
  });

  const columns = [
    { title: "Title", dataIndex: "title", key: "title" },
    {
      title: "Scope",
      dataIndex: "scope",
      key: "scope",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: TemplateData) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => setEditingTemplate(record)}
          />
          <Button
            icon={<CopyOutlined />}
            size="small"
            onClick={() => setDuplicatingTemplate(record)}
            title="Duplicate"
          />
          <Popconfirm
            title="Delete this template?"
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
          Create Template
        </Button>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={templates || []}
          renderItem={(template) => (
            <Card
              size="small"
              style={{ marginBottom: 8 }}
              actions={[
                <Button
                  icon={<EditOutlined />}
                  type="link"
                  onClick={() => setEditingTemplate(template)}
                />,
                <Button
                  icon={<CopyOutlined />}
                  type="link"
                  onClick={() => setDuplicatingTemplate(template)}
                  title="Duplicate"
                />,
                <Popconfirm
                  title="Delete?"
                  onConfirm={() => deleteMutation.mutate(template.id)}
                >
                  <Button icon={<DeleteOutlined />} type="link" danger />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={template.title}
                description={
                  <Space direction="vertical" size={2}>
                    <Tag>{template.scope}</Tag>
                  </Space>
                }
              />
            </Card>
          )}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={templates || []}
          rowKey="id"
          loading={isLoading}
        />
      )}

      <TemplateForm
        open={!!editingTemplate || creating}
        template={creating ? null : editingTemplate}
        onClose={() => {
          setEditingTemplate(null);
          setCreating(false);
        }}
      />

      <TemplateForm
        open={!!duplicatingTemplate}
        template={null}
        duplicateFrom={duplicatingTemplate}
        onClose={() => setDuplicatingTemplate(null)}
      />
    </div>
  );
}

export default TemplateList;
