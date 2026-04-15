import { api } from "./client";

export interface WireGuardStatus {
  workspace_id: string;
  cidr: string | null;
  status: "pending" | "connected" | "stale";
  last_handshake_at: string | null;
}

export interface ProvisionResponse {
  workspace_id: string;
  cidr: string;
  hub_address: string;
  gateway_address: string;
  public_key: string;
  config: string;
  status: "pending" | "connected" | "stale";
}

export async function provisionWireGuard(workspaceId: string) {
  const { data } = await api.post<ProvisionResponse>(
    `/api/workspaces/${workspaceId}/wireguard/provision`
  );
  return data;
}

export async function getWireGuardConfig(workspaceId: string) {
  const { data } = await api.get<{ cidr: string; config: string; status: string }>(
    `/api/workspaces/${workspaceId}/wireguard/config`
  );
  return data;
}

export async function getWireGuardStatus(workspaceId: string) {
  const { data } = await api.get<WireGuardStatus>(
    `/api/workspaces/${workspaceId}/wireguard/status`
  );
  return data;
}

export async function deprovisionWireGuard(workspaceId: string) {
  await api.post(`/api/workspaces/${workspaceId}/wireguard/deprovision`);
}
