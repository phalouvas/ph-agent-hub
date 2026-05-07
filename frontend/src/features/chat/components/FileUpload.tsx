// =============================================================================
// PH Agent Hub — FileUpload
// =============================================================================
// Ant Design Upload; POST /chat/session/:id/upload; disabled for temporary sessions.
// =============================================================================

import React from "react";
import { Upload, Button, message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd";
import { getToken } from "../../../services/api";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

interface FileUploadProps {
  sessionId: string;
  disabled?: boolean;
  onUploadComplete?: () => void;
}

export function FileUpload({
  sessionId,
  disabled,
  onUploadComplete,
}: FileUploadProps) {
  const [fileList, setFileList] = React.useState<UploadFile[]>([]);

  return (
    <Upload
      fileList={fileList}
      onChange={({ file, fileList: newList }) => {
        setFileList(newList);
        if (file.status === "done") {
          message.success(`${file.name} uploaded`);
          onUploadComplete?.();
        } else if (file.status === "error") {
          message.error(`${file.name} upload failed`);
        }
      }}
      action={`${BASE_URL}/chat/session/${sessionId}/upload`}
      headers={{
        Authorization: `Bearer ${getToken()}`,
      }}
      disabled={disabled}
      showUploadList={{ showRemoveIcon: true }}
    >
      <Button icon={<UploadOutlined />} disabled={disabled}>
        Upload File
      </Button>
    </Upload>
  );
}

export default FileUpload;
