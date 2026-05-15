// =============================================================================
// PH Agent Hub — Admin TenantList
// =============================================================================
// Admin only; Ant Design Table/List with server-side search, sorting, pagination.
// =============================================================================

import { useState, useEffect } from "react";
import {
  Table,
  Button,
  Space,
  Popconfirm,
  Checkbox,
  message,
  Grid,
  List,
  Card,
  Typography,
  Input,
} from "antd";
import { EditOutlined, DeleteOutlined, SearchOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTenants,
  deleteTenant,
  TenantData,
} from "../../services/admin";
import { useAdminTable } from "../../hooks/useAdminTable";
import { useDebounce } from "../../hooks/useDebounce";
import { TenantForm } from "./TenantForm";
import { formatCurrency } from "../../../../shared/utils/formatCurrency";

const { useBreakpoint } = Grid;
const { Text } = Typography;

export function TenantList() {
  const [editingTenant, setEditingTenant] = useState<TenantData | null>(null);
  const [creating, setCreating] = useState(false);
  const [forceDelete, setForceDelete] = useState(false);
  const [searchText, setSearchText] = useState("");
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const queryClient = useQueryClient();

  const debouncedSearch = useDebounce(searchText, 300);

  const { data, isLoading, updateParams, handleTableChange, setSearch } = useAdminTable(
    ["admin-tenants"],
    (p) => listTenants({ ...p }),
  );

  useEffect(() => {
    setSearch(debouncedSearch || undefined);
  }, [debouncedSearch, setSearch]);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTenant(id, { force: forceDelete }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-tenants"] });
      message.success("Tenant deleted");
      setForceDelete(false);
    },
    onError: (error: Error) => {
      message.error(error.message || "Failed to delete tenant");
    },
  });

  const columns = [
    { title: "Name", dataIndex: "name", key: "name", sorter: true },
    {
      title: "Cost",
      dataIndex: "total_cost",
      key: "total_cost",
      sorter: true,
      render: (v: number) => formatCurrency(v),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      sorter: true,
      render: (v: string) => new Date(v).toLocaleDateString(),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: TenantData) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => setEditingTenant(record)}
          />
          <Popconfirm
            title={
              forceDelete
                ? "⚠️ This will PERMANENTLY delete the tenant AND ALL related data (users, sessions, files, etc.). Continue?"
                : "Delete this tenant?"
            }
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const tenantsData = data?.items || [];
  const totalTenants = data?.total || 0;

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button type="primary" onClick={() => setCreating(true)}>
          Create Tenant
        </Button>
        <Checkbox
          checked={forceDelete}
          onChange={(e) => setForceDelete(e.target.checked)}
        >
          Force delete (cascade all data)
        </Checkbox>
        <Input
          placeholder="Search by name…"
          prefix={<SearchOutlined />}
          allowClear
          value={searchText}
          onChange={(e) => {
            setSearchText(e.target.value);
            updateParams({ page: 1 });
          }}
          style={{ width: 220 }}
        />
      </Space>

      {isMobile ? (
        <List
          loading={isLoading}
          dataSource={tenantsData}
          pagination={{
            current: data?.page || 1,
            pageSize: data?.page_size || 25,
            total: totalTenants,
            onChange: (p) => updateParams({ page: p }),
            showSizeChanger: false,
          }}
          renderItem={(tenant) => (
            <Card
              size="small"
              style={{ marginBottom: 8 }}
              actions={[
                <Button
                  icon={<EditOutlined />}
                  type="link"
                  onClick={() => setEditingTenant(tenant)}
                />,
                <Popconfirm
                  title={
                    forceDelete
                      ? "⚠️ This will PERMANENTLY delete the tenant AND ALL related data. Continue?"
                      : "Delete?"
                  }
                  onConfirm={() => deleteMutation.mutate(tenant.id)}
                >
                  <Button icon={<DeleteOutlined />} type="link" danger />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                title={tenant.name}
                description={
                  <Text type="secondary">
                    Created: {new Date(tenant.created_at).toLocaleDateString()}
                  </Text>
                }
              />
            </Card>
          )}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={tenantsData}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: data?.page || 1,
            pageSize: data?.page_size || 25,
            total: totalTenants,
            showSizeChanger: true,
            pageSizeOptions: ["10", "25", "50", "100"],
            showTotal: (total, range) => `${range[0]}-${range[1]} of ${total}`,
          }}
          onChange={handleTableChange}
        />
      )}

      <TenantForm
        open={!!editingTenant || creating}
        tenant={creating ? null : editingTenant}
        onClose={() => {
          setEditingTenant(null);
          setCreating(false);
        }}
      />
    </div>
  );
}

export default TenantList;
