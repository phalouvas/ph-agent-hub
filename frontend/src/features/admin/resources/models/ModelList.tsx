// =============================================================================
// PH Agent Hub — Admin ModelList
// =============================================================================
// Ant Design Table/List; api_key field masked.
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
  listModels,
  deleteModel,
  updateModel,
  ModelData,
} from "../../services/admin";
import { ModelForm } from "./ModelForm";

const { useBreakpoint } = Grid;
const { Text } = Typography;

export function ModelList() {
  const [editingModel, setEditingModel] = useState<ModelData | null>(null);
  const [creating, setCreating] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();

  const { data: models, isLoading } = useQuery({
    queryKey: ["admin-models"],
    queryFn: listModels,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
      message.success("Model deleted");
    },
  });

  const toggleEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateModel(id, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
    },
  });

  const columns = [
    { title: "Name", dataIndex: "name", key: "name" },
    {
      title: "Provider",
      dataIndex: "provider",
      key: "provider",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "Model ID",
      dataIndex: "model_id",
      key: "model_id",
      render: (v: string | null) =>
        v ? <Text code>{v}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: "API Key",
      key: "api_key",
      render: () => <Text type="secondary">••••••••</Text>,
    },
    {
      title: "Max Tokens",
      dataIndex: "max_tokens",
      key: "max_tokens",
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      render: (_: boolean, record: ModelData) => (
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
      render: (_: unknown, record: ModelData) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => setEditingModel(record)}
          />
          <Popconfirm
            title="Delete this model?"
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
          Add Model
        </Button>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={models || []}
          renderItem={(model) => (
            <Card
              size="small"
              style={{ marginBottom: 8 }}
              actions={[
                <Button
                  icon={<EditOutlined />}
                  type="link"
                  onClick={() => setEditingModel(model)}
                />,
                <Popconfirm
                  title="Delete?"
                  onConfirm={() => deleteMutation.mutate(model.id)}
                >
                  <Button icon={<DeleteOutlined />} type="link" danger />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={model.name}
                description={
                  <Space direction="vertical" size={2}>
                    <Tag>{model.provider}</Tag>
                    <Text type="secondary">
                      Max tokens: {model.max_tokens} · Temp: {model.temperature}
                    </Text>
                    <Switch
                      checked={model.enabled}
                      onChange={(checked) =>
                        toggleEnabled.mutate({
                          id: model.id,
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
          dataSource={models || []}
          rowKey="id"
          loading={isLoading}
        />
      )}

      <ModelForm
        open={!!editingModel || creating}
        model={creating ? null : editingModel}
        onClose={() => {
          setEditingModel(null);
          setCreating(false);
        }}
      />
    </div>
  );
}

export default ModelList;
