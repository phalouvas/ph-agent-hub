// =============================================================================
// PH Agent Hub — MessageFeedback
// =============================================================================
// Thumbs up/down; POST /chat/session/:id/message/:msgId/feedback.
// =============================================================================

import { useState } from "react";
import { Button, Space, message } from "antd";
import {
  LikeOutlined,
  DislikeOutlined,
  LikeFilled,
  DislikeFilled,
} from "@ant-design/icons";
import { submitFeedback } from "../services/chat";

interface MessageFeedbackProps {
  sessionId: string;
  messageId: string;
}

export function MessageFeedback({
  sessionId,
  messageId,
}: MessageFeedbackProps) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);

  const handleFeedback = async (r: "up" | "down") => {
    try {
      await submitFeedback(sessionId, messageId, r);
      setRating(r);
      message.success(r === "up" ? "Thanks for your feedback!" : "Feedback noted");
    } catch {
      message.error("Failed to submit feedback");
    }
  };

  return (
    <Space size="small">
      <Button
        type="text"
        size="small"
        icon={rating === "up" ? <LikeFilled /> : <LikeOutlined />}
        onClick={() => handleFeedback("up")}
      />
      <Button
        type="text"
        size="small"
        icon={rating === "down" ? <DislikeFilled /> : <DislikeOutlined />}
        onClick={() => handleFeedback("down")}
      />
    </Space>
  );
}

export default MessageFeedback;
