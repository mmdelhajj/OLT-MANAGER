import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { me } from "@/api/auth";
import {
  getWireGuardStatus,
  provisionWireGuard,
  ProvisionResponse,
} from "@/api/wireguard";

export default function WireGuardPage() {
  const { wid: paramWid } = useParams<{ wid: string }>();
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const workspaceId = paramWid ?? meData?.workspaces?.[0];
  const queryClient = useQueryClient();

  const [provisioned, setProvisioned] = useState<ProvisionResponse | null>(null);

  const { data: status } = useQuery({
    queryKey: ["wg-status", workspaceId],
    queryFn: () => getWireGuardStatus(workspaceId!),
    enabled: !!workspaceId,
    refetchInterval: 10_000,
  });

  const provision = useMutation({
    mutationFn: () => provisionWireGuard(workspaceId!),
    onSuccess: (data) => {
      setProvisioned(data);
      queryClient.invalidateQueries({ queryKey: ["wg-status", workspaceId] });
    },
  });

  if (!workspaceId) return <p>No workspace selected.</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">WireGuard</h1>

      <div className="bg-white border rounded-lg p-4 mb-6">
        <p className="text-sm text-slate-500">Workspace status</p>
        <div className="flex items-center gap-2 mt-1">
          <Dot status={status?.status ?? "pending"} />
          <span className="font-medium">{status?.status ?? "pending"}</span>
        </div>
        {status?.cidr && (
          <p className="text-xs text-slate-500 mt-1">Subnet: {status.cidr}</p>
        )}
        {status?.last_handshake_at && (
          <p className="text-xs text-slate-500">
            Last handshake: {new Date(status.last_handshake_at).toLocaleString()}
          </p>
        )}
      </div>

      <button
        onClick={() => provision.mutate()}
        disabled={provision.isPending}
        className="bg-brand-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {provision.isPending ? "Provisioning…" : "Connect this workspace"}
      </button>

      {provisioned && (
        <div className="mt-6">
          <h2 className="font-medium mb-2">One-line install</h2>
          <pre className="bg-slate-900 text-slate-50 text-xs rounded p-4 overflow-x-auto">
            {`curl -sSL https://oltmanager.io/install.sh | sudo bash -s -- \\
  --token <workspace-token>`}
          </pre>

          <h2 className="font-medium mb-2 mt-4">Or download wg-quick config</h2>
          <pre className="bg-slate-100 border rounded p-4 text-xs overflow-x-auto">
            {provisioned.config}
          </pre>
        </div>
      )}
    </div>
  );
}

function Dot({ status }: { status: string }) {
  const color =
    status === "connected"
      ? "bg-green-500"
      : status === "stale"
      ? "bg-amber-500"
      : "bg-slate-400";
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
}
