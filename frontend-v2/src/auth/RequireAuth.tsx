import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

/**
 * Route guard that redirects to /login if there is no JWT in localStorage.
 * Wrap any authenticated route in <RequireAuth>...</RequireAuth>.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const token = localStorage.getItem("olt_jwt");
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
