// =============================================================================
// PH Agent Hub — Admin SettingsPage
// =============================================================================
// Admin only; stub (no backend data model yet per Phase 9 notes).
// =============================================================================

import { Card, Typography, Empty } from "antd";
import { SettingOutlined } from "@ant-design/icons";

const { Title, Paragraph } = Typography;

export function SettingsPage() {
  return (
    <div>
      <Title level={4}>Settings</Title>
      <Card>
        <Empty
          image={<SettingOutlined style={{ fontSize: 64 }} />}
          description={
            <div>
              <Paragraph>
                System settings are not yet configurable through the UI.
              </Paragraph>
              <Paragraph type="secondary">
                Platform configuration (rate limits, default models, agent timeouts,
                etc.) will be available in a future update.
              </Paragraph>
            </div>
          }
        />
      </Card>
    </div>
  );
}

export default SettingsPage;
