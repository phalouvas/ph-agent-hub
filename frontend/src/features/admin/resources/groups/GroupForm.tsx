// =============================================================================
// PH Agent Hub — Admin GroupForm
// =============================================================================
// Ant Design Create/Edit Modal+Form for user groups.
// =============================================================================

import React from "react";
import { Modal, Form, Input, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createGroup, updateGroup, GroupData } from "../../services/admin";

interface GroupFormProps {
  open: boolean;
  group: GroupData | null;
  onClose: () => void;
}

export function GroupForm({ open, group, onClose }: GroupFormProps) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const isEdit = !!group;

  React.useEffect(() => {
    if (open) {
      if (group) {
        form.setFieldsValue({ name: group.name });
      } else {
        form.resetFields();
      }
    }
  }, [open, group, form]);

  const createMutation = useMutation({
    mutationFn: (data: { name: string }) => createGroup(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-groups"] });
      message.success("Group created");
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string } }) =>
      updateGroup(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-groups"] });
      message.success("Group updated");
      onClose();
    },
  });

  return (
    <Modal
      title={isEdit ? "Edit Group" : "Create Group"}
      open={open}
      onOk={async () => {
        const values = await form.validateFields();
        if (isEdit) {
          await updateMutation.mutateAsync({ id: group!.id, data: values });
        } else {
          await createMutation.mutateAsync(values);
        }
      }}
      onCancel={onClose}
      confirmLoading={createMutation.isPending || updateMutation.isPending}
      width={400}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label="Group Name"
          rules={[{ required: true, message: "Please enter a group name" }]}
        >
          <Input placeholder="e.g., Engineering Team" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default GroupForm;
