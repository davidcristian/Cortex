// Test harness glue (excluded from coverage): jest-dom matchers + DOM cleanup between tests.
// Cleanup is registered here rather than relying on vitest globals (we import test APIs explicitly).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
