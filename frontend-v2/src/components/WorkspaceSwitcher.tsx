import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { me } from "@/api/auth";

export default function WorkspaceSwitcher() {
  const navigate = useNavigate();
  const { wid } = useParams<{ wid: string }>();
  const { data } = useQuery({ queryKey: ["me"], queryFn: me });

  if (!data?.workspaces?.length) {
    return null;
  }

  return (
    <select
      className="border rounded px-2 py-1 text-sm bg-white"
      value={wid ?? data.workspaces[0]}
      onChange={(e) => navigate(`/app/workspaces/${e.target.value}/dashboard`)}
    >
      {data.workspaces.map((w) => (
        <option key={w} value={w}>
          {w.slice(0, 8)}…
        </option>
      ))}
    </select>
  );
}
