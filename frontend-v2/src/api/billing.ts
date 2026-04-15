import { api } from "./client";

export async function startCheckout(plan: "starter" | "pro" | "scale") {
  const { data } = await api.post<{ checkout_url: string; session_id: string }>(
    "/api/billing/checkout",
    { plan }
  );
  return data;
}

export async function openBillingPortal() {
  const { data } = await api.post<{ portal_url: string }>("/api/billing/portal");
  return data;
}
