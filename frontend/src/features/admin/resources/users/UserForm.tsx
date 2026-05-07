// =============================================================================
// PH Agent Hub — Admin UserForm
// =============================================================================
// Ant Design Create/Edit Modal+Form; role selector (admin: any role;
// manager: user only).
// =============================================================================

import React from "react";
import { Modal, Form, Input, Select, Switch, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../../../providers/AuthProvider";
import { createUser, updateUser, UserData } from "../../services/admin";

interface UserFormProps {
  open: boolean;
  user: UserData | null;
  onClose: () => void;
}

export function UserForm({ open, user, onClose }: UserFormProps) {
  const [form] = Form.useForm();
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const isEdit = !!user;
  const isAdmin = currentUser?.role === "admin";

  React.useEffect(() => {
    if (open) {
      if (user) {
        form.setFieldsValue({
          email: user.email,
          display_name: user.display_name,
          role: user.role,
          is_active: user.is_active,
          tenant_id: user.tenant_id,
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          role: "user",
          is_active: true,
        });
      }
    }
  }, [open, user, form]);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createUser(data as Partial<UserData> & { password: string }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      message.success("User created");
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      updateUser(id, data as Partial<UserData> & { password?: string }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      message.success("User updated");
      onClose();
    },
  });

  const handleOk = async () => {
    const values = await form.validateFields();
    if (isEdit) {
      // Only send changed fields
      const data: Record<string, unknown> = {};
      if (values.email !== user!.email) data.email = values.email;
      if (values.display_name !== user!.display_name) data.display_name = values.display_name;
      if (values.role !== user!.role) data.role = values.role;
      if (values.is_active !== user!.is_active) data.is_active = values.is_active;
      if (values.password) data.password = values.password;
      if (isAdmin && values.tenant_id !== user!.tenant_id) data.tenant_id = values.tenant_id;
      if (Object.keys(data).length === 0) {
        onClose();
        return;
      }
      await updateMutation.mutateAsync({ id: user!.id, data });
    } else {
      await createMutation.mutateAsync(values);
    }
  };

  return (
    <Modal
      title={isEdit ? "Edit User" : "Create User"}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={createMutation.isPending || updateMutation.isPending}
      width={480}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="email"
          label="Email"
          rules={[{ required: true, type: "email" }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="display_name"
          label="Display Name"
          rules={[{ required: true }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="password" label="Password">
          <Input.Password
            placeholder={
              isEdit ? "Leave blank to keep current" : "Enter password"
            }
          />
        </Form.Item>
        <Form.Item name="role" label="Role" rules={[{ required: true }]}>
          <Select
            options={
              isAdmin
                ? [
                    { label: "User", value: "user" },
                    { label: "Manager", value: "manager" },
                    { label: "Admin", value: "admin" },
                  ]
                : [{ label: "User", value: "user" }]
            }
          />
        </Form.Item>
        <Form.Item name="is_active" label="Active" valuePropName="checked">
          <Switch />
        </Form.Item>
        {isAdmin && (
          <Form.Item name="tenant_id" label="Tenant ID">
            <Input placeholder="Tenant ID (admin only)" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}

export default UserForm;
