import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import TrialBanner from "@/components/TrialBanner";

function renderBanner(billing: { plan: string; plan_name: string }, status: string) {
  return render(
    <MemoryRouter>
      <TrialBanner billing={billing} status={status} />
    </MemoryRouter>,
  );
}

describe("TrialBanner", () => {
  it("renders nothing for active tenants", () => {
    const { container } = renderBanner(
      { plan: "pro", plan_name: "Pro" },
      "active",
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the trial CTA for trial tenants", () => {
    renderBanner({ plan: "trial", plan_name: "Trial" }, "trial");
    expect(screen.getByText(/you're on the trial trial/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upgrade/i })).toHaveAttribute(
      "href",
      "/app/settings/billing",
    );
  });

  it("shows the past_due warning for delinquent tenants", () => {
    renderBanner({ plan: "pro", plan_name: "Pro" }, "past_due");
    expect(screen.getByText(/your last payment failed/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /update billing/i })).toHaveAttribute(
      "href",
      "/app/settings/billing",
    );
  });
});
