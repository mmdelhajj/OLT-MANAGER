import { useQuery } from "@tanstack/react-query";

import { me } from "@/api/auth";
import { startCheckout, openBillingPortal } from "@/api/billing";

const PLANS: Array<{ key: "starter" | "pro" | "scale"; name: string; price: string }> = [
  { key: "starter", name: "Starter", price: "$49/mo" },
  { key: "pro", name: "Pro", price: "$199/mo" },
  { key: "scale", name: "Scale", price: "$799/mo" },
];

export default function BillingPage() {
  const { data } = useQuery({ queryKey: ["me"], queryFn: me });

  async function upgrade(plan: "starter" | "pro" | "scale") {
    const { checkout_url } = await startCheckout(plan);
    window.location.assign(checkout_url);
  }

  async function manage() {
    const { portal_url } = await openBillingPortal();
    window.location.assign(portal_url);
  }

  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Billing</h1>

      <div className="bg-white border rounded-lg p-4 mb-6">
        <p className="text-sm text-slate-500">Current plan</p>
        <p className="text-xl font-medium">{data.billing.plan_name}</p>
        <p className="text-xs text-slate-500 mt-2">
          OLTs: {data.billing.usage.olts ?? 0} / {data.billing.limits.olts}{" "}
          &middot; ONUs: {data.billing.usage.onus ?? 0} /{" "}
          {data.billing.limits.onus}
        </p>
        {data.billing.plan !== "trial" && (
          <button
            onClick={manage}
            className="mt-4 bg-slate-700 text-white px-4 py-2 rounded text-sm"
          >
            Manage subscription
          </button>
        )}
      </div>

      <h2 className="font-medium mb-2">Upgrade</h2>
      <div className="grid md:grid-cols-3 gap-4">
        {PLANS.map((p) => (
          <div key={p.key} className="bg-white border rounded-lg p-4">
            <p className="font-medium">{p.name}</p>
            <p className="text-2xl my-2">{p.price}</p>
            <button
              onClick={() => upgrade(p.key)}
              disabled={data.billing.plan === p.key}
              className="w-full bg-brand-600 text-white py-2 rounded disabled:opacity-50"
            >
              {data.billing.plan === p.key ? "Current" : "Upgrade"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
