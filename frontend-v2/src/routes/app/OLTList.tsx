import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listOLTs } from "@/api/olts";

export default function OLTList() {
  const { wid } = useParams<{ wid: string }>();
  const { data: olts = [] } = useQuery({
    queryKey: ["olts", wid],
    queryFn: () => listOLTs(wid!),
    enabled: !!wid,
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">OLTs</h1>
      <table className="w-full bg-white border rounded-lg overflow-hidden">
        <thead className="bg-slate-100 text-left text-xs uppercase">
          <tr>
            <th className="px-4 py-2">Name</th>
            <th className="px-4 py-2">IP</th>
            <th className="px-4 py-2">Model</th>
            <th className="px-4 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {olts.map((olt) => (
            <tr key={olt.id} className="border-t">
              <td className="px-4 py-2">
                <Link
                  to={`/app/workspaces/${wid}/olts/${olt.id}`}
                  className="text-brand-600"
                >
                  {olt.name}
                </Link>
              </td>
              <td className="px-4 py-2 font-mono text-xs">{olt.ip_address}</td>
              <td className="px-4 py-2">{olt.model}</td>
              <td className="px-4 py-2">
                <span
                  className={
                    olt.is_online
                      ? "text-green-600"
                      : "text-red-600"
                  }
                >
                  {olt.is_online ? "online" : "offline"}
                </span>
              </td>
            </tr>
          ))}
          {olts.length === 0 && (
            <tr>
              <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                No OLTs in this workspace yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
