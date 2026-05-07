// =============================================================================
// PH Agent Hub — Admin AnalyticsPage
// =============================================================================
// GET /admin/usage; Ant Design Statistic+Table; admin sees all tenants,
// manager sees own.
// =============================================================================

import {
  Card,
  Statistic,
  Row,
  Col,
  Table,
  Typography,
  Spin,
  Empty,
} from "antd";
import {
  BarChartOutlined,
  ApiOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../../../providers/AuthProvider";
import { listUsage, UsageData } from "../../services/admin";

const { Title } = Typography;

export function AnalyticsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const { data: usage, isLoading } = useQuery({
    queryKey: ["admin-usage"],
    queryFn: () => listUsage(isAdmin ? undefined : { tenant_id: user?.tenant_id }),
  });

  const totalTokensIn =
    usage?.reduce((sum, u) => sum + u.tokens_in, 0) || 0;
  const totalTokensOut =
    usage?.reduce((sum, u) => sum + u.tokens_out, 0) || 0;
  const uniqueUsers = new Set(usage?.map((u) => u.user_id) || []).size;
  const uniqueModels = new Set(usage?.map((u) => u.model_id) || []).size;

  const columns = [
    {
      title: "Date",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => new Date(v).toLocaleString(),
    },
    { title: "User", dataIndex: "user_id", key: "user_id", ellipsis: true },
    { title: "Model", dataIndex: "model_id", key: "model_id", ellipsis: true },
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
      title: "Total",
      key: "total",
      render: (_: unknown, r: UsageData) =>
        (r.tokens_in + r.tokens_out).toLocaleString(),
    },
  ];

  return (
    <div>
      <Title level={4}>Usage Analytics</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Total Tokens In"
              value={totalTokensIn}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Total Tokens Out"
              value={totalTokensOut}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Unique Users"
              value={uniqueUsers}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
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
        />
      )}
    </div>
  );
}

export default AnalyticsPage;
