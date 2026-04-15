import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import WorkspaceSwitcher from "@/components/WorkspaceSwitcher";

const meMock = vi.fn();
const navigateMock = vi.fn();

vi.mock("@/api/auth", () => ({
  me: () => meMock(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

beforeEach(() => {
  meMock.mockReset();
  navigateMock.mockReset();
});

function renderSwitcher(initialPath = "/app/workspaces/ws-aaaa-1111/dashboard") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/app/workspaces/:wid/*" element={<WorkspaceSwitcher />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("WorkspaceSwitcher", () => {
  it("renders nothing when the user has no workspaces", async () => {
    meMock.mockResolvedValueOnce({
      user: { id: "u", email: "x", role: "owner", email_verified: true },
      tenant: { id: "t", name: "T", slug: "t", status: "active" },
      workspaces: [],
      billing: { plan: "trial", plan_name: "Trial", limits: {}, usage: {} },
    });
    const { container } = renderSwitcher();
    // Wait for the query to settle.
    await screen.findByText((_, el) => el?.tagName === "BODY", { exact: false }).catch(() => null);
    expect(container.querySelector("select")).toBeNull();
  });

  it("renders an option per workspace and navigates on change", async () => {
    meMock.mockResolvedValueOnce({
      user: { id: "u", email: "x", role: "owner", email_verified: true },
      tenant: { id: "t", name: "T", slug: "t", status: "active" },
      workspaces: ["ws-aaaa-1111", "ws-bbbb-2222"],
      billing: { plan: "pro", plan_name: "Pro", limits: {}, usage: {} },
    });
    renderSwitcher();

    const select = (await screen.findByRole("combobox")) as HTMLSelectElement;
    expect(select.options).toHaveLength(2);

    fireEvent.change(select, { target: { value: "ws-bbbb-2222" } });
    expect(navigateMock).toHaveBeenCalledWith(
      "/app/workspaces/ws-bbbb-2222/dashboard",
    );
  });
});
