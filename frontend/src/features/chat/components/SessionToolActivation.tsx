// =============================================================================
// PH Agent Hub — SessionToolActivation
// =============================================================================
// Ant Design Drawer+Switch list; GET/POST/DELETE /chat/session/:id/tools.
// =============================================================================

import {
  Drawer,
  List,
  Switch,
  Typography,
  Empty,
  Space,
  message,
  Tooltip,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../services/api";
import {
  listSessionTools,
  addSessionTool,
  removeSessionTool,
  setToolAlwaysOn,
  listAlwaysOnTools,
  ToolData,
} from "../services/chat";

const { Text } = Typography;

interface SessionToolActivationProps {
  sessionId: string;
  open: boolean;
  onClose: () => void;
}

export function SessionToolActivation({
  sessionId,
  open,
  onClose,
}: SessionToolActivationProps) {
  const queryClient = useQueryClient();

  // Available tools for the tenant
  const { data: availableTools, isLoading: loadingAvailable } = useQuery({
    queryKey: ["session-tools-available", sessionId],
    queryFn: () => api<ToolData[]>("/chat/session/tools/available"),
    enabled: open,
  });

  // Active tools for this session
  const { data: activeTools, isLoading: loadingActive } = useQuery({
    queryKey: ["session-tools", sessionId],
    queryFn: () => listSessionTools(sessionId),
    enabled: open,
  });

  // Always-on tool IDs for this user
  const { data: alwaysOnIds } = useQuery({
    queryKey: ["always-on-tools"],
    queryFn: listAlwaysOnTools,
    enabled: open,
  });

  const alwaysOnSet = new Set(alwaysOnIds || []);
  const activeIds = new Set((activeTools || []).map((t) => t.id));

  const addMutation = useMutation({
    mutationFn: (toolId: string) => addSessionTool(sessionId, toolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["session-tools", sessionId] });
    },
    onError: () => message.error("Failed to add tool"),
  });

  const removeMutation = useMutation({
    mutationFn: (toolId: string) => removeSessionTool(sessionId, toolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["session-tools", sessionId] });
    },
    onError: () => message.error("Failed to remove tool"),
  });

  const alwaysOnMutation = useMutation({
    mutationFn: ({ toolId, alwaysOn }: { toolId: string; alwaysOn: boolean }) =>
      setToolAlwaysOn(toolId, alwaysOn),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["always-on-tools"] });
    },
    onError: () => message.error("Failed to update always-on preference"),
  });

  const handleToggle = (toolId: string, checked: boolean) => {
    if (checked) {
      addMutation.mutate(toolId);
    } else {
      removeMutation.mutate(toolId);
    }
  };

  return (
    <Drawer
      title="Session Tools"
      open={open}
      onClose={onClose}
      width={420}
    >
      <List
        loading={loadingAvailable || loadingActive}
        dataSource={availableTools || []}
        locale={{
          emptyText: (
            <Empty description="No tools available for your tenant" />
          ),
        }}
        renderItem={(tool) => (
          <List.Item
            actions={[
              <Tooltip title="Auto-activate in new sessions" key="always">
                <Switch
                  size="small"
                  checked={alwaysOnSet.has(tool.id)}
                  onChange={(checked) =>
                    alwaysOnMutation.mutate({
                      toolId: tool.id,
                      alwaysOn: checked,
                    })
                  }
                  loading={alwaysOnMutation.isPending}
                />
              </Tooltip>,
              <Switch
                key="active"
                checked={activeIds.has(tool.id)}
                onChange={(checked) => handleToggle(tool.id, checked)}
                loading={
                  addMutation.isPending || removeMutation.isPending
                }
              />,
            ]}
          >
            <List.Item.Meta
              title={tool.name}
              description={
                <Space direction="vertical" size={0}>
                  <Text type="secondary">
                    Type: {tool.type}
                    {alwaysOnSet.has(tool.id) ? " · Always on" : ""}
                  </Text>
                  {tool.enabled ? null : (
                    <Text type="danger">Disabled</Text>
                  )}
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </Drawer>
  );
}

export default SessionToolActivation;
