import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { register } from "@/api/auth";

export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    company_name: "",
    full_name: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth = await register(form);
      localStorage.setItem("olt_jwt", auth.access_token);
      localStorage.setItem("olt_tenant_id", auth.tenant_id);
      navigate("/app/workspaces", { replace: true });
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail ?? "Signup failed";
      setError(typeof detail === "string" ? detail : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md bg-white shadow rounded-lg p-8 space-y-4"
      >
        <h1 className="text-2xl font-semibold">Start your trial</h1>
        <p className="text-sm text-slate-600">
          14 days free, no credit card. Cancel anytime.
        </p>

        <label className="block">
          <span className="text-sm">Company name</span>
          <input
            required
            value={form.company_name}
            onChange={(e) => update("company_name", e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm">Your name</span>
          <input
            value={form.full_name}
            onChange={(e) => update("full_name", e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm">Email</span>
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm">Password</span>
          <input
            type="password"
            required
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
          <span className="text-xs text-slate-500">
            8+ chars with uppercase, lowercase, and a number
          </span>
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-brand-600 text-white py-2 rounded hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create account"}
        </button>

        <p className="text-sm text-center pt-2">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-600">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
