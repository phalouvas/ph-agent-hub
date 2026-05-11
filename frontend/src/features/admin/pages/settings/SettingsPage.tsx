// =============================================================================
// PH Agent Hub — Admin SettingsPage
// =============================================================================
// Admin only; manages application-wide settings (starting with currency).
// =============================================================================

import { Card, Typography, Form, Select, Button, message, Spin } from "antd";
import { SettingOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSettings, updateSettings } from "../../services/admin";
import { setCurrency } from "../../../../shared/utils/formatCurrency";

const { Title } = Typography;

const CURRENCY_OPTIONS = [
  { value: "EUR", label: "€  EUR" },
  { value: "USD", label: "$  USD" },
  { value: "GBP", label: "£  GBP" },
  { value: "JPY", label: "¥  JPY" },
  { value: "CNY", label: "¥  CNY" },
];

export function SettingsPage() {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: settingsData, isLoading } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: getSettings,
  });

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      if (data.settings.currency) {
        setCurrency(data.settings.currency);
      }
      message.success("Settings saved");
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
    },
    onError: () => {
      message.error("Failed to save settings");
    },
  });

  if (isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin />
      </div>
    );
  }

  const currentCurrency = settingsData?.settings?.currency || "EUR";
  // Keep the formatCurrency utility in sync on first load
  setCurrency(currentCurrency);

  const handleSave = (values: Record<string, string>) => {
    mutation.mutate(values);
  };

  return (
    <div>
      <Title level={4}>
        <SettingOutlined /> Settings
      </Title>
      <Card style={{ maxWidth: 500 }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ currency: currentCurrency }}
          onFinish={handleSave}
        >
          <Form.Item
            name="currency"
            label="Currency"
            tooltip="Used to format cost values across the app"
          >
            <Select options={CURRENCY_OPTIONS} />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={mutation.isPending}
            >
              Save
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}

export default SettingsPage;
