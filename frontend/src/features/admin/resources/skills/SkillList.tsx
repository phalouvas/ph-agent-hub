// =============================================================================
// PH Agent Hub — Admin SkillList
// =============================================================================
// Ant Design Table/List.
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
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listSkills,
  deleteSkill,
  updateSkill,
  SkillData,
} from "../../services/admin";
import { SkillForm } from "./SkillForm";

const { useBreakpoint } = Grid;
const { Text } = Typography;

export function SkillList() {
  const [editingSkill, setEditingSkill] = useState<SkillData | null>(null);
  const [creating, setCreating] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get("tenant_id") || undefined;

  const { data: skills, isLoading } = useQuery({
    queryKey: ["admin-skills", tenantId],
    queryFn: () => listSkills({ tenant_id: tenantId }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSkill,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-skills"] });
      message.success("Skill deleted");
    },
  });

  const toggleEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateSkill(id, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-skills"] });
    },
  });

  const columns = [
    { title: "Title", dataIndex: "title", key: "title" },
    {
      title: "Type",
      dataIndex: "execution_type",
      key: "execution_type",
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: "MAF Key",
      dataIndex: "maf_target_key",
      key: "maf_target_key",
    },
    {
      title: "Visibility",
      dataIndex: "visibility",
      key: "visibility",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      render: (_: boolean, record: SkillData) => (
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
      render: (_: unknown, record: SkillData) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => setEditingSkill(record)}
          />
          <Popconfirm
            title="Delete this skill?"
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
          Create Skill
        </Button>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={skills || []}
          renderItem={(skill) => (
            <Card
              size="small"
              style={{ marginBottom: 8 }}
              actions={[
                <Button
                  icon={<EditOutlined />}
                  type="link"
                  onClick={() => setEditingSkill(skill)}
                />,
                <Popconfirm
                  title="Delete?"
                  onConfirm={() => deleteMutation.mutate(skill.id)}
                >
                  <Button icon={<DeleteOutlined />} type="link" danger />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={skill.title}
                description={
                  <Space direction="vertical" size={2}>
                    <Space>
                      <Tag color="blue">{skill.execution_type}</Tag>
                      <Tag>{skill.visibility}</Tag>
                    </Space>
                    <Text type="secondary">{skill.maf_target_key}</Text>
                    <Switch
                      checked={skill.enabled}
                      onChange={(checked) =>
                        toggleEnabled.mutate({
                          id: skill.id,
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
          dataSource={skills || []}
          rowKey="id"
          loading={isLoading}
        />
      )}

      <SkillForm
        open={!!editingSkill || creating}
        skill={creating ? null : editingSkill}
        onClose={() => {
          setEditingSkill(null);
          setCreating(false);
        }}
      />
    </div>
  );
}

export default SkillList;
