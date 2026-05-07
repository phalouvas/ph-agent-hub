// =============================================================================
// PH Agent Hub — PromptLibrary
// =============================================================================
// Ant Design Drawer+List; GET/POST/PUT/DELETE /prompts; user-owned.
// =============================================================================

import { useState } from "react";
import {
  Drawer,
  List,
  Button,
  Typography,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
  message,
  Empty,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  BookOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../services/api";

const { Paragraph } = Typography;
const { TextArea } = Input;

interface PromptData {
  id: string;
  tenant_id: string;
  user_id: string;
  template_id: string | null;
  title: string;
  description: string;
  content: string;
  visibility: string;
  created_at: string;
  updated_at: string;
}

interface PromptLibraryProps {
  onSelect?: (promptId: string) => void;
  selectedPromptId?: string;
}

export function PromptLibrary({
  onSelect,
  selectedPromptId,
}: PromptLibraryProps) {
  const [open, setOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<PromptData | null>(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: prompts, isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => api<PromptData[]>("/prompts"),
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: (data: {
      title: string;
      description: string;
      content: string;
      visibility: string;
    }) => api<PromptData>("/prompts", { method: "POST", body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      message.success("Prompt created");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<PromptData>;
    }) => api<PromptData>(`/prompts/${id}`, { method: "PUT", body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      message.success("Prompt updated");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api<void>(`/prompts/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      message.success("Prompt deleted");
    },
  });

  const handleSave = async () => {
    const values = await form.validateFields();
    if (editingPrompt) {
      await updateMutation.mutateAsync({ id: editingPrompt.id, data: values });
    } else {
      await createMutation.mutateAsync(values);
    }
    setEditingPrompt(null);
    form.resetFields();
  };

  const handleEdit = (prompt: PromptData) => {
    setEditingPrompt(prompt);
    form.setFieldsValue(prompt);
  };

  const handleDelete = async (id: string) => {
    await deleteMutation.mutateAsync(id);
  };

  const handleNew = () => {
    setEditingPrompt({} as PromptData);
    form.resetFields();
  };

  return (
    <>
      <Button
        icon={<BookOutlined />}
        onClick={() => setOpen(true)}
        type="text"
      >
        Prompts
      </Button>

      <Drawer
        title="Prompt Library"
        open={open}
        onClose={() => {
          setOpen(false);
          setEditingPrompt(null);
        }}
        width={480}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleNew}
          >
            New Prompt
          </Button>
        }
      >
        <List
          loading={isLoading}
          dataSource={prompts || []}
          locale={{ emptyText: <Empty description="No prompts yet" /> }}
          renderItem={(item) => (
            <List.Item
              actions={[
                onSelect && (
                  <Button
                    type={
                      selectedPromptId === item.id ? "primary" : "default"
                    }
                    size="small"
                    onClick={() => onSelect(item.id)}
                  >
                    Use
                  </Button>
                ),
                <Button
                  icon={<EditOutlined />}
                  size="small"
                  onClick={() => handleEdit(item)}
                />,
                <Popconfirm
                  title="Delete this prompt?"
                  onConfirm={() => handleDelete(item.id)}
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
                title={item.title}
                description={
                  <Paragraph
                    ellipsis={{ rows: 2 }}
                    style={{ margin: 0 }}
                  >
                    {item.content}
                  </Paragraph>
                }
              />
            </List.Item>
          )}
        />

        {/* Edit/Create Modal */}
        <Modal
          title={editingPrompt?.id ? "Edit Prompt" : "New Prompt"}
          open={!!editingPrompt}
          onOk={handleSave}
          onCancel={() => setEditingPrompt(null)}
          confirmLoading={
            createMutation.isPending || updateMutation.isPending
          }
          width={640}
        >
          <Form form={form} layout="vertical">
            <Form.Item
              name="title"
              label="Title"
              rules={[{ required: true }]}
            >
              <Input />
            </Form.Item>
            <Form.Item name="description" label="Description">
              <TextArea rows={2} />
            </Form.Item>
            <Form.Item
              name="content"
              label="Content"
              rules={[{ required: true }]}
            >
              <TextArea rows={8} />
            </Form.Item>
            <Form.Item name="visibility" label="Visibility" initialValue="private">
              <Select
                options={[
                  { label: "Private", value: "private" },
                  { label: "Shared", value: "shared" },
                  { label: "Public", value: "public" },
                ]}
              />
            </Form.Item>
          </Form>
        </Modal>
      </Drawer>
    </>
  );
}

export default PromptLibrary;
