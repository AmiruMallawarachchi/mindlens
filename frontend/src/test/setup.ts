import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// React Testing Library only auto-cleans when the test framework exposes a
// global `afterEach`; Vitest runs without globals here, so unmount explicitly.
afterEach(() => {
  cleanup();
});
