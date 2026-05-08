// =============================================================================
// PH Agent Hub — Admin GroupList
// =============================================================================
// TanStack Query + Ant Design Table; inline expandable panels for member
// and model management; mobile Card fallback.
// =============================================================================

import { useState } from "react";
import {
  Table,
  Button,
  Space,
  Tag,
  Card,
  Grid,
  Popconfirm,
  Select,
  message,
  Typography,
  Row,
  Col,
  List,
  Empty,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  UsergroupAddOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listGroups,
  deleteGroup,
  listGroupMembers,
  addGroupMember,
  removeGroupMember,
  listGroupModels,
  assignModelToGroup,
  removeModelFromGroup,
  listUsers,
  listModels,
  GroupData,
  GroupMemberData,
  GroupModelData,
} from "../../services/admin";
import { GroupForm } from "./GroupForm";

const { Text } = Typography;
const { useBreakpoint } = Grid;

export function GroupList() {
  const queryClient = useQueryClient();
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  const [formOpen, setFormOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<GroupData | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const { data: groups, isLoading } = useQuery({
    queryKey: ["admin-groups"],
    queryFn: listGroups,
  });

  const { data: users } = useQuery({
    queryKey: ["admin-users"],
    queryFn: listUsers,
  });

  const { data: models } = useQuery({
    queryKey: ["admin-models"],
    queryFn: listModels,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-groups"] });
      message.success("Group deleted");
    },
  });

  const handleEdit = (group: GroupData) => {
    setEditingGroup(group);
    setFormOpen(true);
  };

  const handleCreate = () => {
    setEditingGroup(null);
    setFormOpen(true);
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (name: string, record: GroupData) => (
        <Button
          type="link"
          style={{ padding: 0 }}
          onClick={() =>
            setExpandedKey(expandedKey === record.id ? null : record.id)
          }
        >
          {name}
        </Button>
      ),
    },
    {
      title: "# Members",
      key: "member_count",
      width: 120,
      render: (_: unknown, record: GroupData) => (
        <MemberCount groupId={record.id} />
      ),
    },
    {
      title: "# Models",
      key: "model_count",
      width: 120,
      render: (_: unknown, record: GroupData) => (
        <ModelCount groupId={record.id} />
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 160,
      render: (_: unknown, record: GroupData) => (
        <Space>
          <Button size="small" onClick={() => handleEdit(record)}>
            Edit
          </Button>
          <Popconfirm
            title="Delete this group?"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const expandedRowRender = (record: GroupData) => (
    <ExpandablePanels groupId={record.id} users={users || []} models={models || []} />
  );

  return (
    <div style={{ padding: isMobile ? 8 : 24 }}>
      <Space
        style={{
          marginBottom: 16,
          width: "100%",
          justifyContent: "space-between",
        }}
      >
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>
          Groups
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          Create Group
        </Button>
      </Space>

      {isMobile ? (
        <div>
          {groups?.map((group) => (
            <Card
              key={group.id}
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Button
                  type="link"
                  style={{ padding: 0 }}
                  onClick={() =>
                    setExpandedKey(expandedKey === group.id ? null : group.id)
                  }
                >
                  {group.name}
                </Button>
              }
              extra={
                <Space>
                  <Button size="small" onClick={() => handleEdit(group)}>
                    Edit
                  </Button>
                  <Popconfirm
                    title="Delete this group?"
                    onConfirm={() => deleteMutation.mutate(group.id)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              }
            >
              <Space>
                <Tag>
                  <MemberCount groupId={group.id} /> members
                </Tag>
                <Tag>
                  <ModelCount groupId={group.id} /> models
                </Tag>
              </Space>
              {expandedKey === group.id && (
                <ExpandablePanels
                  groupId={group.id}
                  users={users || []}
                  models={models || []}
                />
              )}
            </Card>
          ))}
        </div>
      ) : (
        <Table
          dataSource={groups}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          expandable={{
            expandedRowRender,
            expandedRowKeys: expandedKey ? [expandedKey] : [],
            onExpand: (_, record) =>
              setExpandedKey(expandedKey === record.id ? null : record.id),
          }}
        />
      )}

      <GroupForm
        open={formOpen}
        group={editingGroup}
        onClose={() => {
          setFormOpen(false);
          setEditingGroup(null);
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper: Member count badge
// ---------------------------------------------------------------------------

function MemberCount({ groupId }: { groupId: string }) {
  const { data: members } = useQuery({
    queryKey: ["admin-group-members", groupId],
    queryFn: () => listGroupMembers(groupId),
  });
  return <>{members?.length ?? 0}</>;
}

function ModelCount({ groupId }: { groupId: string }) {
  const { data: models } = useQuery({
    queryKey: ["admin-group-models", groupId],
    queryFn: () => listGroupModels(groupId),
  });
  return <>{models?.length ?? 0}</>;
}

// ---------------------------------------------------------------------------
// Expandable panels: members + models
// ---------------------------------------------------------------------------

function ExpandablePanels({
  groupId,
  users,
  models,
}: {
  groupId: string;
  users: { id: string; email: string; display_name: string }[];
  models: { id: string; name: string; provider: string }[];
}) {
  const queryClient = useQueryClient();

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ["admin-group-members", groupId],
    queryFn: () => listGroupMembers(groupId),
  });

  const { data: groupModels, isLoading: modelsLoading } = useQuery({
    queryKey: ["admin-group-models", groupId],
    queryFn: () => listGroupModels(groupId),
  });

  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

  const addMemberMutation = useMutation({
    mutationFn: (userId: string) => addGroupMember(groupId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-group-members", groupId] });
      setSelectedUserId(null);
      message.success("Member added");
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userId: string) => removeGroupMember(groupId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-group-members", groupId] });
      message.success("Member removed");
    },
  });

  const assignModelMutation = useMutation({
    mutationFn: (modelId: string) => assignModelToGroup(groupId, modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-group-models", groupId] });
      setSelectedModelId(null);
      message.success("Model assigned");
    },
  });

  const removeModelMutation = useMutation({
    mutationFn: (modelId: string) => removeModelFromGroup(groupId, modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-group-models", groupId] });
      message.success("Model removed");
    },
  });

  const memberIds = new Set((members || []).map((m) => m.id));
  const modelIds = new Set((groupModels || []).map((m) => m.id));

  const availableUsers = users.filter((u) => !memberIds.has(u.id));
  const availableModels = models.filter((m) => !modelIds.has(m.id));

  return (
    <Row gutter={16} style={{ marginTop: 8 }}>
      <Col xs={24} md={12}>
        <Card
          size="small"
          title={
            <Space>
              <UsergroupAddOutlined />
              <span>Members</span>
            </Space>
          }
        >
          <Space direction="vertical" style={{ width: "100%" }}>
            <Space.Compact style={{ width: "100%" }}>
              <Select
                placeholder="Add user..."
                value={selectedUserId}
                onChange={setSelectedUserId}
                style={{ flex: 1 }}
                showSearch
                optionFilterProp="label"
                options={availableUsers.map((u) => ({
                  label: `${u.display_name} (${u.email})`,
                  value: u.id,
                }))}
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                disabled={!selectedUserId}
                loading={addMemberMutation.isPending}
                onClick={() =>
                  selectedUserId && addMemberMutation.mutate(selectedUserId)
                }
              />
            </Space.Compact>

            {membersLoading ? (
              <Text type="secondary">Loading...</Text>
            ) : (members?.length ?? 0) === 0 ? (
              <Empty description="No members" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                size="small"
                dataSource={members}
                renderItem={(item: GroupMemberData) => (
                  <List.Item
                    actions={[
                      <Button
                        key="remove"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        loading={removeMemberMutation.isPending}
                        onClick={() => removeMemberMutation.mutate(item.id)}
                      />,
                    ]}
                  >
                    <List.Item.Meta
                      title={item.display_name || item.email}
                      description={item.role}
                    />
                  </List.Item>
                )}
              />
            )}
          </Space>
        </Card>
      </Col>

      <Col xs={24} md={12}>
        <Card
          size="small"
          title={
            <Space>
              <ApiOutlined />
              <span>Models</span>
            </Space>
          }
        >
          <Space direction="vertical" style={{ width: "100%" }}>
            <Space.Compact style={{ width: "100%" }}>
              <Select
                placeholder="Assign model..."
                value={selectedModelId}
                onChange={setSelectedModelId}
                style={{ flex: 1 }}
                showSearch
                optionFilterProp="label"
                options={availableModels.map((m) => ({
                  label: `${m.name} (${m.provider})`,
                  value: m.id,
                }))}
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                disabled={!selectedModelId}
                loading={assignModelMutation.isPending}
                onClick={() =>
                  selectedModelId && assignModelMutation.mutate(selectedModelId)
                }
              />
            </Space.Compact>

            {modelsLoading ? (
              <Text type="secondary">Loading...</Text>
            ) : (groupModels?.length ?? 0) === 0 ? (
              <Empty
                description="No models assigned"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : (
              <List
                size="small"
                dataSource={groupModels}
                renderItem={(item: GroupModelData) => (
                  <List.Item
                    actions={[
                      <Button
                        key="remove"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        loading={removeModelMutation.isPending}
                        onClick={() => removeModelMutation.mutate(item.id)}
                      />,
                    ]}
                  >
                    <List.Item.Meta
                      title={item.name}
                      description={
                        <Space>
                          <Tag>{item.provider}</Tag>
                          {!item.enabled && <Tag color="red">Disabled</Tag>}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Space>
        </Card>
      </Col>
    </Row>
  );
}

export default GroupList;
