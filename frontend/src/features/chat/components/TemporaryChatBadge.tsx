// =============================================================================
// PH Agent Hub — TemporaryChatBadge
// =============================================================================
// Ant Design Tag; visible when session.is_temporary=true.
// =============================================================================

import { Tag } from "antd";
import { ClockCircleOutlined } from "@ant-design/icons";

interface TemporaryChatBadgeProps {
  isTemporary: boolean;
}

export function TemporaryChatBadge({ isTemporary }: TemporaryChatBadgeProps) {
  if (!isTemporary) return null;
  return (
    <Tag icon={<ClockCircleOutlined />} color="orange">
      Temporary
    </Tag>
  );
}

export default TemporaryChatBadge;
