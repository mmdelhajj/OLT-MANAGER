import { Routes, Route, Navigate } from "react-router-dom";

import LoginPage from "./routes/auth/LoginPage";
import SignupPage from "./routes/auth/SignupPage";
import ForgotPasswordPage from "./routes/auth/ForgotPasswordPage";
import VerifyEmailPage from "./routes/auth/VerifyEmailPage";
import AppShell from "./routes/app/AppShell";
import WorkspaceList from "./routes/app/WorkspaceList";
import WorkspaceDashboard from "./routes/app/WorkspaceDashboard";
import OLTList from "./routes/app/OLTList";
import OLTDetail from "./routes/app/OLTDetail";
import ONUList from "./routes/app/ONUList";
import TrafficPage from "./routes/app/TrafficPage";
import AlarmsPage from "./routes/app/AlarmsPage";
import BillingPage from "./routes/app/BillingPage";
import TeamPage from "./routes/app/TeamPage";
import WireGuardPage from "./routes/app/WireGuardPage";
import { RequireAuth } from "./auth/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />

      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/verify-email/:token" element={<VerifyEmailPage />} />

      {/* Authenticated app */}
      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="workspaces" replace />} />
        <Route path="workspaces" element={<WorkspaceList />} />
        <Route path="workspaces/:wid">
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<WorkspaceDashboard />} />
          <Route path="olts" element={<OLTList />} />
          <Route path="olts/:oid" element={<OLTDetail />} />
          <Route path="onus" element={<ONUList />} />
          <Route path="traffic" element={<TrafficPage />} />
          <Route path="alarms" element={<AlarmsPage />} />
        </Route>
        <Route path="settings/billing" element={<BillingPage />} />
        <Route path="settings/team" element={<TeamPage />} />
        <Route path="settings/wireguard" element={<WireGuardPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
