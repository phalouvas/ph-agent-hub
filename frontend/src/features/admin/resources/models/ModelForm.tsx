// =============================================================================
// PH Agent Hub — Admin ModelForm
// =============================================================================
// Ant Design Create/Edit Modal+Form; api_key input type=password.
// =============================================================================

import React from "react";
import {
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  message,
} from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createModel, updateModel, ModelData } from "../../services/admin";

interface ModelFormProps {
  open: boolean;
  model: ModelData | null;
  onClose: () => void;
}

export function ModelForm({ open, model, onClose }: ModelFormProps) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const isEdit = !!model;

  React.useEffect(() => {
    if (open) {
      if (model) {
        form.setFieldsValue({
          name: model.name,
          provider: model.provider,
          base_url: model.base_url,
          enabled: model.enabled,
          max_tokens: model.max_tokens,
          temperature: model.temperature,
          routing_priority: model.routing_priority,
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          enabled: true,
          max_tokens: 4096,
          temperature: 0.7,
          routing_priority: 0,
        });
      }
    }
  }, [open, model, form]);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createModel(data as Partial<ModelData> & { api_key: string }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
      message.success("Model created");
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
    }) => updateModel(id, data as Partial<ModelData> & { api_key?: string }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
      message.success("Model updated");
      onClose();
    },
  });

  return (
    <Modal
      title={isEdit ? "Edit Model" : "Add Model"}
      open={open}
      onOk={async () => {
        const values = await form.validateFields();
        if (isEdit) {
          await updateMutation.mutateAsync({
            id: model!.id,
            data: values,
          });
        } else {
          await createMutation.mutateAsync(values);
        }
      }}
      onCancel={onClose}
      confirmLoading={createMutation.isPending || updateMutation.isPending}
      width={520}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item
          name="provider"
          label="Provider"
          rules={[{ required: true }]}
        >
          <Select
            options={[
              { label: "OpenAI", value: "openai" },
              { label: "Anthropic", value: "anthropic" },
              { label: "DeepSeek", value: "deepseek" },
            ]}
          />
        </Form.Item>
        <Form.Item name="api_key" label="API Key">
          <Input.Password
            placeholder={
              isEdit ? "Leave blank to keep current" : "Enter API key"
            }
          />
        </Form.Item>
        <Form.Item name="base_url" label="Base URL">
          <Input placeholder="e.g., https://api.openai.com/v1" />
        </Form.Item>
        <Form.Item name="max_tokens" label="Max Tokens">
          <InputNumber min={1} max={128000} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="temperature" label="Temperature">
          <InputNumber min={0} max={2} step={0.1} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="routing_priority" label="Routing Priority">
          <InputNumber min={0} max={100} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="enabled" label="Enabled" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default ModelForm;
