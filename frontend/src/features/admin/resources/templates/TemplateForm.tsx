// =============================================================================
// PH Agent Hub — Admin TemplateForm
// =============================================================================
// Ant Design Create/Edit Modal+Form; tool_ids multi-select.
// =============================================================================

import React from "react";
import {
  Modal,
  Form,
  Input,
  Select,
  message,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createTemplate,
  updateTemplate,
  TemplateData,
  listTools,
  listModels,
} from "../../services/admin";

const { TextArea } = Input;

interface TemplateFormProps {
  open: boolean;
  template: TemplateData | null;
  onClose: () => void;
}

export function TemplateForm({ open, template, onClose }: TemplateFormProps) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const isEdit = !!template;

  const { data: tools } = useQuery({
    queryKey: ["admin-tools"],
    queryFn: listTools,
    enabled: open,
  });

  const { data: models } = useQuery({
    queryKey: ["admin-models"],
    queryFn: listModels,
    enabled: open,
  });

  React.useEffect(() => {
    if (open) {
      if (template) {
        form.setFieldsValue({
          title: template.title,
          description: template.description,
          system_prompt: template.system_prompt,
          scope: template.scope,
          default_model_id: template.default_model_id,
          tool_ids: template.tool_ids || [],
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          scope: "tenant",
          tool_ids: [],
        });
      }
    }
  }, [open, template, form]);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createTemplate(data as unknown as Partial<TemplateData>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-templates"] });
      message.success("Template created");
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Record<string, unknown>;
    }) => updateTemplate(id, data as unknown as Partial<TemplateData>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-templates"] });
      message.success("Template updated");
      onClose();
    },
  });

  return (
    <Modal
      title={isEdit ? "Edit Template" : "Create Template"}
      open={open}
      onOk={async () => {
        const values = await form.validateFields();
        if (isEdit) {
          await updateMutation.mutateAsync({
            id: template!.id,
            data: values,
          });
        } else {
          await createMutation.mutateAsync(values);
        }
      }}
      onCancel={onClose}
      confirmLoading={createMutation.isPending || updateMutation.isPending}
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
        <Form.Item
          name="description"
          label="Description"
          rules={[{ required: true }]}
        >
          <TextArea rows={2} />
        </Form.Item>
        <Form.Item
          name="system_prompt"
          label="System Prompt"
          rules={[{ required: true }]}
        >
          <TextArea rows={6} />
        </Form.Item>
        <Form.Item name="scope" label="Scope">
          <Select
            options={[
              { label: "Tenant", value: "tenant" },
              { label: "User", value: "user" },
            ]}
          />
        </Form.Item>
        <Form.Item name="default_model_id" label="Default Model">
          <Select
            allowClear
            placeholder="Select default model"
            options={(models || []).map((m) => ({
              label: `${m.name} (${m.provider})`,
              value: m.id,
            }))}
          />
        </Form.Item>
        <Form.Item name="tool_ids" label="Tools">
          <Select
            mode="multiple"
            allowClear
            placeholder="Select tools"
            options={(tools || []).map((t) => ({
              label: t.name,
              value: t.id,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default TemplateForm;
