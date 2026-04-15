import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { verifyEmail } from "@/api/auth";

export default function VerifyEmailPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"pending" | "ok" | "error">("pending");

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }
    verifyEmail(token)
      .then(() => setState("ok"))
      .catch(() => setState("error"));
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-white shadow rounded-lg p-8 space-y-4 text-center">
        {state === "pending" && <p>Verifying…</p>}
        {state === "ok" && (
          <>
            <h1 className="text-xl font-semibold">Email verified ✓</h1>
            <Link to="/app" className="text-brand-600 inline-block">
              Continue to dashboard
            </Link>
          </>
        )}
        {state === "error" && (
          <>
            <h1 className="text-xl font-semibold">Link is invalid or expired</h1>
            <Link to="/login" className="text-brand-600">
              Back to sign in
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
