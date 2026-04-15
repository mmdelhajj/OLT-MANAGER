import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listOLTs } from "@/api/olts";

export default function WorkspaceDashboard() {
  const { wid } = useParams<{ wid: string }>();
  const { data: olts = [], isLoading } = useQuery({
    queryKey: ["olts", wid],
    queryFn: () => listOLTs(wid!),
    enabled: !!wid,
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Dashboard</h1>
      {isLoading && <p>Loading…</p>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat label="OLTs" value={olts.length} />
        <Stat
          label="Online OLTs"
          value={olts.filter((o) => o.is_online).length}
        />
        <Stat
          label="Offline OLTs"
          value={olts.filter((o) => !o.is_online).length}
        />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-3xl font-semibold mt-1">{value}</p>
    </div>
  );
}
