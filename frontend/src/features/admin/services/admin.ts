// =============================================================================
// PH Agent Hub — Admin API Service
// =============================================================================
// All admin API calls: /admin/users, /admin/tenants, /admin/models,
// /admin/tools, /admin/templates, /admin/skills, /admin/usage, /admin/logs,
// /admin/audit. Calls api.ts.
// =============================================================================

import api from "../../../services/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserData {
  id: string;
  email: string;
  display_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantData {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ModelData {
  id: string;
  tenant_id: string;
  name: string;
  model_id: string;
  provider: string;
  base_url: string | null;
  enabled: boolean;
  max_tokens: number;
  temperature: number;
  routing_priority: number;
  created_at: string;
  updated_at: string;
}

export interface ToolData {
  id: string;
  tenant_id: string;
  name: string;
  type: string;
  config: Record<string, unknown> | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateData {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  system_prompt: string;
  scope: string;
  default_model_id: string | null;
  assigned_user_id: string | null;
  created_at: string;
  updated_at: string;
  tool_ids: string[];
}

export interface SkillData {
  id: string;
  tenant_id: string;
  user_id: string | null;
  title: string;
  description: string;
  execution_type: string;
  maf_target_key: string;
  visibility: string;
  template_id: string | null;
  default_prompt_id: string | null;
  default_model_id: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  tool_ids: string[];
}

export interface UsageData {
  id: string;
  tenant_id: string;
  user_id: string;
  model_id: string;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
}

export interface AuditData {
  id: string;
  tenant_id: string | null;
  actor_id: string;
  actor_role: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export function listUsers(): Promise<UserData[]> {
  return api<UserData[]>("/admin/users");
}

export function getUser(id: string): Promise<UserData> {
  return api<UserData>(`/admin/users/${id}`);
}

export function createUser(data: Partial<UserData> & { password?: string }): Promise<UserData> {
  return api<UserData>("/admin/users", { method: "POST", body: data });
}

export function updateUser(id: string, data: Partial<UserData> & { password?: string }): Promise<UserData> {
  return api<UserData>(`/admin/users/${id}`, { method: "PUT", body: data });
}

export function deleteUser(id: string): Promise<void> {
  return api<void>(`/admin/users/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Tenants (admin-only)
// ---------------------------------------------------------------------------

export function listTenants(): Promise<TenantData[]> {
  return api<TenantData[]>("/admin/tenants");
}

export function createTenant(data: { name: string }): Promise<TenantData> {
  return api<TenantData>("/admin/tenants", { method: "POST", body: data });
}

export function updateTenant(id: string, data: { name: string }): Promise<TenantData> {
  return api<TenantData>(`/admin/tenants/${id}`, { method: "PUT", body: data });
}

export function deleteTenant(id: string): Promise<void> {
  return api<void>(`/admin/tenants/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export function listModels(): Promise<ModelData[]> {
  return api<ModelData[]>("/admin/models");
}

export function getModel(id: string): Promise<ModelData> {
  return api<ModelData>(`/admin/models/${id}`);
}

export function createModel(data: Partial<ModelData> & { api_key?: string }): Promise<ModelData> {
  return api<ModelData>("/admin/models", { method: "POST", body: data });
}

export function updateModel(id: string, data: Partial<ModelData> & { api_key?: string }): Promise<ModelData> {
  return api<ModelData>(`/admin/models/${id}`, { method: "PUT", body: data });
}

export function deleteModel(id: string): Promise<void> {
  return api<void>(`/admin/models/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

export function listTools(): Promise<ToolData[]> {
  return api<ToolData[]>("/admin/tools");
}

export function getTool(id: string): Promise<ToolData> {
  return api<ToolData>(`/admin/tools/${id}`);
}

export function createTool(data: Partial<ToolData>): Promise<ToolData> {
  return api<ToolData>("/admin/tools", { method: "POST", body: data });
}

export function updateTool(id: string, data: Partial<ToolData>): Promise<ToolData> {
  return api<ToolData>(`/admin/tools/${id}`, { method: "PUT", body: data });
}

export function deleteTool(id: string): Promise<void> {
  return api<void>(`/admin/tools/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

export function listTemplates(): Promise<TemplateData[]> {
  return api<TemplateData[]>("/admin/templates");
}

export function getTemplate(id: string): Promise<TemplateData> {
  return api<TemplateData>(`/admin/templates/${id}`);
}

export function createTemplate(data: Partial<TemplateData>): Promise<TemplateData> {
  return api<TemplateData>("/admin/templates", { method: "POST", body: data });
}

export function updateTemplate(id: string, data: Partial<TemplateData>): Promise<TemplateData> {
  return api<TemplateData>(`/admin/templates/${id}`, { method: "PUT", body: data });
}

export function deleteTemplate(id: string): Promise<void> {
  return api<void>(`/admin/templates/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

export function listSkills(): Promise<SkillData[]> {
  return api<SkillData[]>("/admin/skills");
}

export function getSkill(id: string): Promise<SkillData> {
  return api<SkillData>(`/admin/skills/${id}`);
}

export function createSkill(data: Partial<SkillData>): Promise<SkillData> {
  return api<SkillData>("/admin/skills", { method: "POST", body: data });
}

export function updateSkill(id: string, data: Partial<SkillData>): Promise<SkillData> {
  return api<SkillData>(`/admin/skills/${id}`, { method: "PUT", body: data });
}

export function deleteSkill(id: string): Promise<void> {
  return api<void>(`/admin/skills/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Usage & Audit
// ---------------------------------------------------------------------------

export function listUsage(params?: { tenant_id?: string }): Promise<UsageData[]> {
  const query = params?.tenant_id ? `?tenant_id=${params.tenant_id}` : "";
  return api<UsageData[]>(`/admin/usage${query}`);
}

export function listAuditLogs(): Promise<AuditData[]> {
  return api<AuditData[]>("/admin/logs");
}
