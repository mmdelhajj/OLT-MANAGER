import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { me } from "@/api/auth";

export default function WorkspaceList() {
  const { data } = useQuery({ queryKey: ["me"], queryFn: me });

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Workspaces</h1>
      {data?.workspaces?.length ? (
        <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {data.workspaces.map((wid) => (
            <li key={wid}>
              <Link
                to={`/app/workspaces/${wid}/dashboard`}
                className="block bg-white border rounded-lg p-4 hover:shadow"
              >
                <p className="font-medium">{wid.slice(0, 8)}…</p>
                <p className="text-xs text-slate-500">Open dashboard →</p>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-slate-500">No workspaces yet.</p>
      )}
    </div>
  );
}
