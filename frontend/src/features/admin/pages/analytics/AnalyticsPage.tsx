// =============================================================================
// PH Agent Hub — Admin AnalyticsPage
// =============================================================================
// GET /admin/usage; Ant Design Statistic+Table; admin sees all tenants,
// manager sees own. Filtering by tenant + user supported.
// =============================================================================

import { useState } from "react";
import {
  Card,
  Statistic,
  Row,
  Col,
  Table,
  Typography,
  Spin,
  Empty,
  Select,
  Space,
} from "antd";
import {
  BarChartOutlined,
  ApiOutlined,
  TeamOutlined,
  DollarOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../../../providers/AuthProvider";
import {
  listUsage,
  listTenants,
  listUsers,
  UsageData,
} from "../../services/admin";
import { formatCurrency } from "../../../../shared/utils/formatCurrency";

const { Title } = Typography;

export function AnalyticsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [selectedTenantId, setSelectedTenantId] = useState<string | undefined>(
    isAdmin ? undefined : user?.tenant_id,
  );
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>();

  // Fetch tenants for filter dropdown (admin only)
  const { data: tenants } = useQuery({
    queryKey: ["admin-tenants"],
    queryFn: listTenants,
    enabled: isAdmin,
  });

  // Fetch users for the selected tenant
  const { data: users } = useQuery({
    queryKey: ["admin-users", selectedTenantId],
    queryFn: () => listUsers({ tenant_id: selectedTenantId }),
    enabled: !!selectedTenantId,
  });

  const { data: usage, isLoading } = useQuery({
    queryKey: ["admin-usage", selectedTenantId, selectedUserId],
    queryFn: () =>
      listUsage({
        tenant_id: isAdmin ? selectedTenantId : user?.tenant_id,
        user_id: selectedUserId,
      }),
  });

  const totalTokensIn =
    usage?.reduce((sum, u) => sum + u.tokens_in, 0) || 0;
  const totalTokensOut =
    usage?.reduce((sum, u) => sum + u.tokens_out, 0) || 0;
  const totalCost =
    usage?.reduce((sum, u) => sum + (u.cost || 0), 0) || 0;
  const uniqueUsers = new Set(usage?.map((u) => u.user_id) || []).size;
  const uniqueModels = new Set(usage?.map((u) => u.model_id) || []).size;

  const handleTenantChange = (value: string | undefined) => {
    setSelectedTenantId(value);
    setSelectedUserId(undefined);
  };

  const columns = [
    {
      title: "Date",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: "Tenant",
      dataIndex: "tenant_name",
      key: "tenant_name",
      ellipsis: true,
      responsive: ["md" as const],
    },
    {
      title: "User",
      dataIndex: "user_full_name",
      key: "user_full_name",
      ellipsis: true,
      render: (_: unknown, r: UsageData) =>
        r.user_full_name || r.user_email || r.user_id.slice(0, 8),
    },
    {
      title: "Model",
      dataIndex: "model_name",
      key: "model_name",
      ellipsis: true,
    },
    {
      title: "Tokens In",
      dataIndex: "tokens_in",
      key: "tokens_in",
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: "Tokens Out",
      dataIndex: "tokens_out",
      key: "tokens_out",
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: "Cache Hit",
      dataIndex: "cache_hit_tokens",
      key: "cache_hit_tokens",
      render: (v: number | null) => (v != null ? v.toLocaleString() : "-"),
    },
    {
      title: "Cost",
      dataIndex: "cost",
      key: "cost",
      render: (v: number | null) => formatCurrency(v),
    },
  ];

  return (
    <div>
      <Title level={4}>Usage Analytics</Title>

      {/* Filters */}
      {isAdmin && (
        <Space style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="All tenants"
            style={{ width: 200 }}
            value={selectedTenantId}
            onChange={handleTenantChange}
            options={tenants?.map((t) => ({
              value: t.id,
              label: t.name,
            }))}
          />
          {selectedTenantId && (
            <Select
              allowClear
              placeholder="All users"
              style={{ width: 250 }}
              value={selectedUserId}
              onChange={setSelectedUserId}
              options={users?.map((u) => ({
                value: u.id,
                label: `${u.display_name} (${u.email})`,
              }))}
              showSearch
              optionFilterProp="label"
            />
          )}
        </Space>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic
              title="Total Cost"
              value={formatCurrency(totalCost)}
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic
              title="Total Tokens In"
              value={totalTokensIn}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic
              title="Total Tokens Out"
              value={totalTokensOut}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic
              title="Unique Users"
              value={uniqueUsers}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic
              title="Unique Models"
              value={uniqueModels}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      ) : !usage || usage.length === 0 ? (
        <Empty description="No usage data yet" />
      ) : (
        <Table
          columns={columns}
          dataSource={usage}
          rowKey="id"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 900 }}
        />
      )}
    </div>
  );
}

export default AnalyticsPage;
