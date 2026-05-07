// =============================================================================
// PH Agent Hub — MemoryManager
// =============================================================================
// Ant Design Drawer+List; GET/POST/DELETE /memory; shows automatic vs manual entries.
// =============================================================================

import { useState } from "react";
import {
  Drawer,
  List,
  Button,
  Typography,
  Popconfirm,
  message,
  Empty,
  Tag,
  Modal,
  Form,
  Input,
  Space,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listMemory, createMemory, deleteMemory } from "../services/chat";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface MemoryManagerProps {
  open: boolean;
  onClose: () => void;
  sessionId?: string;
}

export function MemoryManager({
  open,
  onClose,
  sessionId,
}: MemoryManagerProps) {
  const [adding, setAdding] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: entries, isLoading } = useQuery({
    queryKey: ["memory", sessionId],
    queryFn: () => listMemory(sessionId),
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: (data: { key: string; value: string }) =>
      createMemory({ ...data, session_id: sessionId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory", sessionId] });
      message.success("Memory entry added");
      setAdding(false);
      form.resetFields();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory", sessionId] });
      message.success("Memory entry deleted");
    },
  });

  const handleAdd = async () => {
    const values = await form.validateFields();
    await createMutation.mutateAsync(values);
  };

  return (
    <Drawer
      title="Memory"
      open={open}
      onClose={onClose}
      width={480}
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setAdding(true)}
        >
          Add Entry
        </Button>
      }
    >
      <List
        loading={isLoading}
        dataSource={entries || []}
        locale={{ emptyText: <Empty description="No memory entries" /> }}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Popconfirm
                title="Delete this entry?"
                onConfirm={() => deleteMutation.mutate(item.id)}
              >
                <Button
                  icon={<DeleteOutlined />}
                  size="small"
                  danger
                />
              </Popconfirm>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <Text strong>{item.key}</Text>
                  <Tag
                    color={
                      item.source === "automatic"
                        ? "blue"
                        : "green"
                    }
                  >
                    {item.source}
                  </Tag>
                </Space>
              }
              description={
                <Paragraph
                  ellipsis={{ rows: 2 }}
                  style={{ margin: 0 }}
                >
                  {item.value}
                </Paragraph>
              }
            />
          </List.Item>
        )}
      />

      <Modal
        title="Add Memory Entry"
        open={adding}
        onOk={handleAdd}
        onCancel={() => {
          setAdding(false);
          form.resetFields();
        }}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="key"
            label="Key"
            rules={[{ required: true }]}
          >
            <Input placeholder="e.g., user_preference" />
          </Form.Item>
          <Form.Item
            name="value"
            label="Value"
            rules={[{ required: true }]}
          >
            <TextArea rows={4} placeholder="Memory value..." />
          </Form.Item>
        </Form>
      </Modal>
    </Drawer>
  );
}

export default MemoryManager;
