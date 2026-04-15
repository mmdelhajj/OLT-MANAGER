import { api } from "./client";

export interface OLT {
  id: number;
  workspace_id: string;
  name: string;
  ip_address: string;
  model: string;
  pon_ports: number;
  is_online: boolean;
}

export async function listOLTs(workspaceId: string): Promise<OLT[]> {
  const { data } = await api.get<OLT[]>("/api/olts", {
    params: { workspace_id: workspaceId },
  });
  return data;
}

export async function getOLT(oltId: number) {
  const { data } = await api.get<OLT>(`/api/olts/${oltId}`);
  return data;
}

export async function createOLT(workspaceId: string, payload: Partial<OLT>) {
  const { data } = await api.post<OLT>("/api/olts", {
    workspace_id: workspaceId,
    ...payload,
  });
  return data;
}

export async function deleteOLT(oltId: number) {
  await api.delete(`/api/olts/${oltId}`);
}
