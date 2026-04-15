import { api } from "./client";

export interface ONU {
  id: number;
  olt_id: number;
  port: number;
  serial: string;
  status: string;
  rx_power: number | null;
  onu_rx_power: number | null;
  uptime: string | null;
}

export async function listONUs(oltId: number): Promise<ONU[]> {
  const { data } = await api.get<ONU[]>(`/api/olts/${oltId}/onus`);
  return data;
}

export async function rebootONU(oltId: number, onuId: number) {
  await api.post(`/api/olts/${oltId}/onus/${onuId}/reboot`);
}
