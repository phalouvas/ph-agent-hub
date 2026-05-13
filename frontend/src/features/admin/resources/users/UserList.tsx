// =============================================================================
// PH Agent Hub — Admin UserList
// =============================================================================
// Ant Design Table on desktop, List/Card on mobile.
// Actions: edit, delete, activate/deactivate, reset password.
// =============================================================================

import { useState } from "react";
import {
  Table,
  Button,
  Space,
  Tag,
  Popconfirm,
  message,
  Switch,
  Grid,
  List,
  Card,
  Typography,
} from "antd";
import {
  EditOutlined,
  DeleteOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listUsers,
  deleteUser,
  updateUser,
  listTenants,
  UserData,
} from "../../services/admin";
import { UserForm } from "./UserForm";
import { formatCurrency } from "../../../../shared/utils/formatCurrency";

const { useBreakpoint } = Grid;
const { Text } = Typography;

export function UserList() {
  const [editingUser, setEditingUser] = useState<UserData | null>(null);
  const [duplicatingUser, setDuplicatingUser] = useState<UserData | null>(null);
  const [creating, setCreating] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get("tenant_id") || undefined;

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users", tenantId],
    queryFn: () => listUsers({ tenant_id: tenantId }),
  });

  const { data: tenants } = useQuery({
    queryKey: ["admin-tenants-user-list"],
    queryFn: () => listTenants(),
  });

  const tenantNameById = new Map((tenants || []).map((t) => [t.id, t.name]));

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      message.success("User deleted");
    },
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateUser(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const columns = [
    { title: "Name", dataIndex: "display_name", key: "display_name" },
    { title: "Email", dataIndex: "email", key: "email" },
    {
      title: "Cost",
      dataIndex: "total_cost",
      key: "total_cost",
      render: (v: number) => formatCurrency(v),
    },
    {
      title: "Role",
      dataIndex: "role",
      key: "role",
      render: (role: string) => (
        <Tag color={role === "admin" ? "red" : role === "manager" ? "blue" : "default"}>
          {role}
        </Tag>
      ),
    },
    {
      title: "Active",
      dataIndex: "is_active",
      key: "is_active",
      render: (_: boolean, record: UserData) => (
        <Switch
          checked={record.is_active}
          onChange={(checked) =>
            toggleActive.mutate({ id: record.id, is_active: checked })
          }
        />
      ),
    },
    {
      title: "Tenant",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 130,
      ellipsis: true,
      responsive: ["lg" as const],
      render: (v: string) => {
        const tenantName = tenantNameById.get(v);
        return tenantName ? (
          <Text>{tenantName}</Text>
        ) : (
          <Text type="secondary">Unknown tenant</Text>
        );
      },
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: UserData) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => setEditingUser(record)}
          />
          <Button
            icon={<CopyOutlined />}
            size="small"
            onClick={() => setDuplicatingUser(record)}
            title="Duplicate"
          />
          <Popconfirm
            title="Delete this user?"
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
          Create User
        </Button>
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={users || []}
          renderItem={(user) => (
            <Card
              size="small"
              style={{ marginBottom: 8 }}
              actions={[
                <Button
                  icon={<EditOutlined />}
                  type="link"
                  onClick={() => setEditingUser(user)}
                />,
                <Button
                  icon={<CopyOutlined />}
                  type="link"
                  onClick={() => setDuplicatingUser(user)}
                  title="Duplicate"
                />,
                <Popconfirm
                  title="Delete?"
                  onConfirm={() => deleteMutation.mutate(user.id)}
                >
                  <Button icon={<DeleteOutlined />} type="link" danger />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={user.display_name}
                description={
                  <Space direction="vertical" size={2}>
                    <Text>{user.email}</Text>
                    <Space>
                      <Tag
                        color={
                          user.role === "admin"
                            ? "red"
                            : user.role === "manager"
                              ? "blue"
                              : "default"
                        }
                      >
                        {user.role}
                      </Tag>
                      <Switch
                        checked={user.is_active}
                        onChange={(checked) =>
                          toggleActive.mutate({
                            id: user.id,
                            is_active: checked,
                          })
                        }
                        size="small"
                      />
                    </Space>
                  </Space>
                }
              />
            </Card>
          )}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={users || []}
          rowKey="id"
          loading={isLoading}
        />
      )}

      <UserForm
        open={!!editingUser || creating}
        user={creating ? null : editingUser}
        onClose={() => {
          setEditingUser(null);
          setCreating(false);
        }}
      />

      <UserForm
        open={!!duplicatingUser}
        user={null}
        duplicateFrom={duplicatingUser}
        onClose={() => setDuplicatingUser(null)}
      />
    </div>
  );
}

export default UserList;
