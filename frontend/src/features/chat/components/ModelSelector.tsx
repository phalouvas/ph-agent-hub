// =============================================================================
// PH Agent Hub — ModelSelector
// =============================================================================
// Ant Design Select; fetches GET /models; pre-selects default;
// supports "Set as default" action via star icon.
// =============================================================================

import React from "react";
import { Select, Space, Typography, Button, Tooltip, message } from "antd";
import { StarOutlined, StarFilled } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { setDefaultModel, getMe } from "../../../services/auth";
import api from "../../../services/api";

const { Text } = Typography;

interface ModelData {
  id: string;
  tenant_id: string;
  name: string;
  provider: string;
  base_url: string | null;
  enabled: boolean;
  thinking_enabled: boolean;
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
  const queryClient = useQueryClient();

  const { data: models, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: () => api<ModelData[]>("/models"),
  });

  const { data: userProfile } = useQuery({
    queryKey: ["user-me"],
    queryFn: getMe,
  });

  const setDefaultMutation = useMutation({
    mutationFn: (modelId: string | null) => setDefaultModel(modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-me"] });
      message.success("Default model updated");
    },
  });

  const defaultModelId = userProfile?.default_model_id;
  const isCurrentDefault = value && value === defaultModelId;

  return (
    <Space direction="vertical" size={0} style={style}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        Model
      </Text>
      <Space.Compact style={{ width: "100%" }}>
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
        {value && (
          <Tooltip
            title={
              isCurrentDefault
                ? "This is your default model"
                : "Set as default model"
            }
          >
            <Button
              icon={isCurrentDefault ? <StarFilled /> : <StarOutlined />}
              onClick={() =>
                setDefaultMutation.mutate(isCurrentDefault ? null : value)
              }
              loading={setDefaultMutation.isPending}
              type={isCurrentDefault ? "primary" : "default"}
            />
          </Tooltip>
        )}
      </Space.Compact>
    </Space>
  );
}

export default ModelSelector;
