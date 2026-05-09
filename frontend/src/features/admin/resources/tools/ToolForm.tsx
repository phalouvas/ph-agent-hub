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
  const [toolType, setToolType] = React.useState(tool?.type ?? "custom");

  React.useEffect(() => {
    if (open) {
      if (tool) {
        const fields: Record<string, unknown> = {
          name: tool.name,
          type: tool.type,
          enabled: tool.enabled,
          is_public: tool.is_public,
        };
        // Populate structured ERPNext fields from config
        if (tool.type === "erpnext" && tool.config) {
          fields.erpnext_base_url = tool.config.base_url || "";
          fields.erpnext_api_key = tool.config.api_key || "";
          fields.erpnext_api_secret = tool.config.api_secret || "";
        }
        // Populate config_json for custom type
        if (tool.type === "custom") {
          fields.config_json = tool.config
            ? JSON.stringify(tool.config, null, 2)
            : "";
        }
        form.setFieldsValue(fields);
        setToolType(tool.type);
      } else {
        form.resetFields();
        form.setFieldsValue({
          type: "custom",
          enabled: true,
          is_public: false,
        });
        setToolType("custom");
      }
    }
  }, [open, tool, form]);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      // Assemble config from structured fields for erpnext
      if (data.type === "erpnext") {
        data.config = {
          base_url: data.erpnext_base_url || "",
          api_key: data.erpnext_api_key || "",
          api_secret: data.erpnext_api_secret || "",
        };
        delete data.erpnext_base_url;
        delete data.erpnext_api_key;
        delete data.erpnext_api_secret;
      } else if (typeof data.config_json === "string" && data.config_json.trim()) {
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
      // Assemble config from structured fields for erpnext
      if (data.type === "erpnext") {
        data.config = {
          base_url: data.erpnext_base_url || "",
          api_key: data.erpnext_api_key || "",
          api_secret: data.erpnext_api_secret || "",
        };
        delete data.erpnext_base_url;
        delete data.erpnext_api_key;
        delete data.erpnext_api_secret;
      } else if (typeof data.config_json === "string" && data.config_json.trim()) {
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
              { label: "Calculator", value: "calculator" },
              { label: "Currency Exchange", value: "currency_exchange" },
              { label: "Custom", value: "custom" },
              { label: "Datetime", value: "datetime" },
              { label: "ERPNext", value: "erpnext" },
              { label: "Fetch URL", value: "fetch_url" },
              { label: "Membrane", value: "membrane" },
              { label: "RSS Feed", value: "rss_feed" },
              { label: "Weather", value: "weather" },
              { label: "Web Search", value: "web_search" },
              { label: "Wikipedia", value: "wikipedia" },
            ]}
            onChange={(value) => setToolType(value)}
          />
        </Form.Item>

        {/* ERPNext-specific structured fields */}
        {toolType === "erpnext" && (
          <>
            <Form.Item
              name="erpnext_base_url"
              label="Base URL"
              rules={[{ required: true, message: "ERPNext site URL is required" }]}
            >
              <Input placeholder="https://erp.example.com" />
            </Form.Item>
            <Form.Item
              name="erpnext_api_key"
              label="API Key"
              rules={[{ required: true, message: "API Key is required" }]}
            >
              <Input placeholder="Your ERPNext API key" />
            </Form.Item>
            <Form.Item
              name="erpnext_api_secret"
              label="API Secret"
              rules={[{ required: true, message: "API Secret is required" }]}
            >
              <Input.Password placeholder="Your ERPNext API secret" />
            </Form.Item>
          </>
        )}

        {/* Config JSON for custom type only */}
        {toolType === "custom" && (
          <Form.Item name="config_json" label="Config (JSON)">
            <TextArea
              rows={6}
              placeholder='{"key": "value"}'
            />
          </Form.Item>
        )}

        <Form.Item name="enabled" label="Enabled" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item
          name="is_public"
          label="Public"
          valuePropName="checked"
          tooltip="When enabled, all tenant users can use this tool regardless of group membership"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default ToolForm;
