// =============================================================================
// PH Agent Hub — MessageBranchNav
// =============================================================================
// Inline branch navigator "2/3 ▶"; calls parent state to switch active branch.
// =============================================================================

import { Button, Space, Typography } from "antd";
import { LeftOutlined, RightOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface BranchInfo {
  currentIndex: number;
  totalBranches: number;
}

interface MessageBranchNavProps {
  branches: BranchInfo | null | undefined;
  onNavigate: (branchIndex: number) => void;
}

export function MessageBranchNav({
  branches,
  onNavigate,
}: MessageBranchNavProps) {
  if (!branches || branches.totalBranches <= 1) return null;

  const { currentIndex, totalBranches } = branches;

  return (
    <Space size={4}>
      <Button
        type="text"
        size="small"
        icon={<LeftOutlined />}
        disabled={currentIndex <= 0}
        onClick={() => onNavigate(currentIndex - 1)}
      />
      <Text type="secondary" style={{ fontSize: 12 }}>
        {currentIndex + 1}/{totalBranches}
      </Text>
      <Button
        type="text"
        size="small"
        icon={<RightOutlined />}
        disabled={currentIndex >= totalBranches - 1}
        onClick={() => onNavigate(currentIndex + 1)}
      />
    </Space>
  );
}

export default MessageBranchNav;
