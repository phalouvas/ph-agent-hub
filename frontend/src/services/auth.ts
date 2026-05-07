// =============================================================================
// PH Agent Hub — Auth Service
// =============================================================================
// login(), logout(), refreshToken(), getMe() — all call api.ts.
// setToken()/getToken() for in-memory JWT storage.
// =============================================================================

import api, { setToken, getToken } from "./api";

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginParams {
  username: string;
  password: string;
}

export async function login(params: LoginParams): Promise<void> {
  const formData = new URLSearchParams();
  formData.append("username", params.username);
  formData.append("password", params.password);

  const data = await api<{ access_token: string; token_type: string }>(
    "/auth/login",
    {
      method: "POST",
      body: formData,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      skipAuth: true,
    },
  );

  setToken(data.access_token);
}

export async function logout(): Promise<void> {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {
    // Silently ignore — we clear the token regardless
  }
  setToken(null);
}

export async function getMe(): Promise<UserProfile> {
  return api<UserProfile>("/auth/me");
}

export { setToken, getToken };
