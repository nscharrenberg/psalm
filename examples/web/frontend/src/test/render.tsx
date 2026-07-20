import { MantineProvider } from "@mantine/core";
import { render as rtlRender } from "@testing-library/react";
import type { ReactElement } from "react";
import { theme } from "../theme";

// NOTE: `export *` must come before the local `export function render` below.
// Vitest/Vite's SSR module transform applies `export * from "..."` in
// source order by assigning each re-exported name onto the module's
// exports object; when it runs after the local `render` export, it
// silently clobbers it with React Testing Library's own `render`
// (dropping the MantineProvider wrapper). Native ESM semantics say a
// local binding should always win over a star re-export of the same
// name, but Vitest's transform doesn't enforce that — so the safe order
// here is re-export first, local declaration second.
export * from "@testing-library/react";

export function render(ui: ReactElement) {
  return rtlRender(
    <MantineProvider theme={theme} forceColorScheme="dark">{ui}</MantineProvider>,
  );
}
