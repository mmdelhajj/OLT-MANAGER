import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getOLT } from "@/api/olts";
import { listONUs } from "@/api/onus";

export default function OLTDetail() {
  const { oid } = useParams<{ oid: string }>();
  const oltId = Number(oid);
  const { data: olt } = useQuery({
    queryKey: ["olt", oltId],
    queryFn: () => getOLT(oltId),
    enabled: !!oltId,
  });
  const { data: onus = [] } = useQuery({
    queryKey: ["onus", oltId],
    queryFn: () => listONUs(oltId),
    enabled: !!oltId,
  });

  if (!olt) return <p>Loading…</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">{olt.name}</h1>
      <p className="text-sm text-slate-500 mb-4">{olt.ip_address}</p>

      <h2 className="font-medium mb-2">ONUs ({onus.length})</h2>
      <ul className="bg-white border rounded-lg divide-y">
        {onus.map((onu) => (
          <li key={onu.id} className="px-4 py-2 flex justify-between text-sm">
            <span className="font-mono">{onu.serial}</span>
            <span className="text-slate-500">port {onu.port}</span>
            <span>{onu.status}</span>
          </li>
        ))}
        {onus.length === 0 && (
          <li className="px-4 py-6 text-center text-slate-500 text-sm">
            No ONUs registered.
          </li>
        )}
      </ul>
    </div>
  );
}
