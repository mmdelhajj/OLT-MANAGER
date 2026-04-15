import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { forgotPassword } from "@/api/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await forgotPassword(email);
    setSent(true);
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-white shadow rounded-lg p-8 space-y-4">
        <h1 className="text-2xl font-semibold">Reset your password</h1>

        {sent ? (
          <p className="text-sm text-slate-700">
            If an account exists for <strong>{email}</strong>, a reset link is on
            its way.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4">
            <input
              type="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border rounded px-3 py-2"
            />
            <button
              type="submit"
              className="w-full bg-brand-600 text-white py-2 rounded hover:bg-brand-700"
            >
              Send reset link
            </button>
          </form>
        )}

        <p className="text-sm text-center">
          <Link to="/login" className="text-brand-600">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
