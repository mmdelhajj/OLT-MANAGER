import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { me } from "@/api/auth";
import WorkspaceSwitcher from "@/components/WorkspaceSwitcher";
import TrialBanner from "@/components/TrialBanner";
import FeedbackWidget from "@/components/FeedbackWidget";

export default function AppShell() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: me });

  function logout() {
    localStorage.removeItem("olt_jwt");
    localStorage.removeItem("olt_tenant_id");
    navigate("/login");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="font-bold text-lg">OLT Manager</span>
            <WorkspaceSwitcher />
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <NavLink to="/app/workspaces" className="hover:text-brand-600">
              Workspaces
            </NavLink>
            <NavLink to="/app/settings/wireguard" className="hover:text-brand-600">
              WireGuard
            </NavLink>
            <NavLink to="/app/settings/billing" className="hover:text-brand-600">
              Billing
            </NavLink>
            <NavLink to="/app/settings/team" className="hover:text-brand-600">
              Team
            </NavLink>
            <button onClick={logout} className="text-slate-500 hover:text-red-600">
              Log out
            </button>
          </nav>
        </div>
      </header>

      {data && <TrialBanner billing={data.billing} status={data.tenant.status} />}

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {isLoading ? <p>Loading…</p> : <Outlet />}
      </main>

      {/* Phase 6 — beta feedback widget, available on every page */}
      <FeedbackWidget />
    </div>
  );
}
