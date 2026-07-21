import { MantineProvider } from "@mantine/core";
import { render as rtlRender, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
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

function AllProviders({ children }: { children: ReactNode }) {
  return <MantineProvider theme={theme} forceColorScheme="dark">{children}</MantineProvider>;
}

// Uses RTL's `wrapper` option (rather than manually wrapping `ui` before
// calling `rtlRender`) specifically so `rerender()` on the returned result
// keeps applying MantineProvider too -- RTL re-renders through the same
// wrapper on every rerender call, but only when it was supplied via this
// option. Manually pre-wrapping `ui` would leave `rerender` unwrapped,
// silently dropping Mantine's context on any test that rerenders.
export function render(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return rtlRender(ui, { wrapper: AllProviders, ...options });
}
