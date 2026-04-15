import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Tear down React Testing Library state between tests so each test gets a
// fresh DOM. Without this, queries can leak across tests and produce
// confusing "found multiple elements" failures.
afterEach(() => {
  cleanup();
});
