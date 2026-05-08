// =============================================================================
// PH Agent Hub — Admin ToolForm
// =============================================================================
// Ant Design Create/Edit Modal+Form; dynamic fields per tool type.
// =============================================================================

import React from "react";
import {
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
} from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createTool, updateTool, ToolData } from "../../services/admin";

const { TextArea } = Input;

interface ToolFormProps {
  open: boolean;
  tool: ToolData | null;
  onClose: () => void;
}

export function ToolForm({ open, tool, onClose }: ToolFormProps) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const isEdit = !!tool;
  const [isPublic, setIsPublic] = React.useState(tool?.is_public ?? false);

  React.useEffect(() => {
    if (open) {
      if (tool) {
        form.setFieldsValue({
          name: tool.name,
          type: tool.type,
          enabled: tool.enabled,
          is_public: tool.is_public,
          config_json: tool.config
            ? JSON.stringify(tool.config, null, 2)
            : "",
        });
        setIsPublic(tool.is_public);
      } else {
        form.resetFields();
        form.setFieldsValue({
          type: "custom",
          enabled: true,
          is_public: false,
        });
        setIsPublic(false);
      }
    }
  }, [open, tool, form]);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      // Parse config JSON if provided
      if (typeof data.config_json === "string" && data.config_json.trim()) {
        try {
          data.config = JSON.parse(data.config_json as string);
        } catch {
          message.error("Invalid JSON in config");
          throw new Error("Invalid JSON");
        }
      }
      delete data.config_json;
      return createTool(data as unknown as Partial<ToolData>);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-tools"] });
      message.success("Tool created");
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
    }) => {
      if (typeof data.config_json === "string" && data.config_json.trim()) {
        try {
          data.config = JSON.parse(data.config_json as string);
        } catch {
          message.error("Invalid JSON in config");
          throw new Error("Invalid JSON");
        }
      }
      delete data.config_json;
      return updateTool(id, data as unknown as Partial<ToolData>);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-tools"] });
      message.success("Tool updated");
      onClose();
    },
  });

  return (
    <Modal
      title={isEdit ? "Edit Tool" : "Create Tool"}
      open={open}
      onOk={async () => {
        const values = await form.validateFields();
        if (isEdit) {
          await updateMutation.mutateAsync({
            id: tool!.id,
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
          name="type"
          label="Type"
          rules={[{ required: true }]}
        >
          <Select
            options={[
              { label: "ERPNext", value: "erpnext" },
              { label: "Membrane", value: "membrane" },
              { label: "Custom", value: "custom" },
              { label: "Datetime", value: "datetime" },
            ]}
          />
        </Form.Item>
        <Form.Item name="config_json" label="Config (JSON)">
          <TextArea
            rows={6}
            placeholder='{"key": "value"}'
          />
        </Form.Item>
        <Form.Item name="enabled" label="Enabled" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item
          name="is_public"
          label="Public"
          valuePropName="checked"
          tooltip="When enabled, all tenant users can use this tool regardless of group membership"
        >
          <Switch onChange={(checked) => setIsPublic(checked)} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default ToolForm;
