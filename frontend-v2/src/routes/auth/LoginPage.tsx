import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { login } from "@/api/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth = await login({ email, password });
      localStorage.setItem("olt_jwt", auth.access_token);
      localStorage.setItem("olt_tenant_id", auth.tenant_id);
      navigate("/app/workspaces", { replace: true });
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail ?? "Login failed";
      setError(typeof detail === "string" ? detail : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm bg-white shadow rounded-lg p-8 space-y-4"
      >
        <h1 className="text-2xl font-semibold">Sign in</h1>

        <label className="block">
          <span className="text-sm text-slate-700">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm text-slate-700">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-brand-600 text-white py-2 rounded hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>

        <div className="flex justify-between text-sm pt-2">
          <Link to="/forgot-password" className="text-brand-600">
            Forgot password?
          </Link>
          <Link to="/signup" className="text-brand-600">
            Create account
          </Link>
        </div>
      </form>
    </div>
  );
}
