import { api } from "./client";

export interface RegisterPayload {
  email: string;
  password: string;
  company_name: string;
  full_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  tenant_id: string;
  role: string;
}

export interface MeResponse {
  user: {
    id: string;
    email: string;
    full_name?: string;
    role: string;
    email_verified: boolean;
  };
  tenant: {
    id: string;
    name: string;
    slug: string;
    status: string;
  };
  workspaces: string[];
  billing: {
    plan: string;
    plan_name: string;
    limits: Record<string, number>;
    usage: Record<string, number>;
  };
}

export async function register(payload: RegisterPayload) {
  const { data } = await api.post<AuthResponse>("/auth/register", payload);
  return data;
}

export async function login(payload: LoginPayload) {
  const { data } = await api.post<AuthResponse>("/auth/login", payload);
  return data;
}

export async function forgotPassword(email: string) {
  await api.post("/auth/forgot-password", { email });
}

export async function resetPassword(token: string, password: string) {
  await api.post("/auth/reset-password", { token, password });
}

export async function verifyEmail(token: string) {
  await api.post("/auth/verify-email", { token });
}

export async function me() {
  const { data } = await api.get<MeResponse>("/auth/me");
  return data;
}
