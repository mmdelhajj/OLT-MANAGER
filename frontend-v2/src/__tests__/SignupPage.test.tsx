import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import SignupPage from "@/routes/auth/SignupPage";

const registerMock = vi.fn();
const navigateMock = vi.fn();

vi.mock("@/api/auth", () => ({
  register: (...args: unknown[]) => registerMock(...args),
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
  registerMock.mockReset();
  navigateMock.mockReset();
  localStorage.clear();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <SignupPage />
    </MemoryRouter>,
  );
}

describe("SignupPage", () => {
  it("renders the trial heading and form fields", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /start your trial/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/company name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("submits the form, stores tokens, and navigates into the app", async () => {
    registerMock.mockResolvedValueOnce({
      access_token: "jwt-abc",
      tenant_id: "tenant-1",
      token_type: "bearer",
      user_id: "user-1",
      role: "owner",
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: "Acme Telecom" },
    });
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "owner@acme.test" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "Sup3rSecure!" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith({
        email: "owner@acme.test",
        password: "Sup3rSecure!",
        company_name: "Acme Telecom",
        full_name: "",
      });
    });

    await waitFor(() => {
      expect(localStorage.getItem("olt_jwt")).toBe("jwt-abc");
      expect(localStorage.getItem("olt_tenant_id")).toBe("tenant-1");
      expect(navigateMock).toHaveBeenCalledWith("/app/workspaces", { replace: true });
    });
  });

  it("surfaces backend errors to the user", async () => {
    registerMock.mockRejectedValueOnce({
      response: { data: { detail: "Email already in use" } },
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: "Acme" },
    });
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "dup@acme.test" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "Whatever1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/email already in use/i)).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
