// =============================================================================
// PH Agent Hub — ModelSelector
// =============================================================================
// Ant Design Select; fetches GET /models; pre-selects default.
// =============================================================================

import React from "react";
import { Select, Space, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import api from "../../../services/api";

const { Text } = Typography;

interface ModelData {
  id: string;
  tenant_id: string;
  name: string;
  provider: string;
  base_url: string | null;
  enabled: boolean;
  max_tokens: number;
  temperature: number;
  routing_priority: number;
  created_at: string;
  updated_at: string;
}

interface ModelSelectorProps {
  value?: string;
  onChange?: (modelId: string) => void;
  style?: React.CSSProperties;
}

export function ModelSelector({ value, onChange, style }: ModelSelectorProps) {
  const { data: models, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: () => api<ModelData[]>("/models"),
  });

  return (
    <Space direction="vertical" size={0} style={style}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        Model
      </Text>
      <Select
        value={value}
        onChange={onChange}
        loading={isLoading}
        placeholder="Select model"
        style={{ minWidth: 160 }}
        allowClear
        options={(models || []).map((m) => ({
          label: `${m.name} (${m.provider})`,
          value: m.id,
        }))}
        notFoundContent={isLoading ? "Loading..." : "No models available"}
      />
    </Space>
  );
}

export default ModelSelector;
