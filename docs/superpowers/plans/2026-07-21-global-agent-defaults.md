# Setup Wizard Global Agent Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible "Set one configuration for all agents" panel to `SetupPage`'s Agents step, collapsed by default, with an "Apply to all agents" button that copies its fields into every agent's config.

**Architecture:** One new `AgentConfigInput` state (`globalConfig`) and one handler function in `SetupPage.tsx`, rendered inside a new single-item `Accordion` above the existing per-agent `Accordion`, reusing the already-existing `AgentConfigPanel` component unchanged.

**Tech Stack:** React 18, TypeScript, Mantine v7 (`Accordion`, `Button`), Vitest + React Testing Library.

## Global Constraints

- No backend changes. The payload sent to `startTrial()` must remain identical in shape to today — `globalConfig` never leaves the browser directly; it's copied into `prosecutor`/`defense`/`judge`/`jury` state before submission, exactly as if a user had typed those values into each agent's own panel.
- Every juror's `seed` field must survive an "Apply to all agents" click untouched — mirror the existing per-juror `onChange` handler's `{ ...updated, seed: j.seed }` pattern.
- A juror added via "Add juror" *after* "Apply to all agents" was clicked must start blank (`emptyJurorConfig()`), not retroactively pick up the global config.
- Clicking "Apply to all agents" while the global panel is entirely blank is allowed (a legitimate bulk-clear) — no validation blocking it.
- Reuse `AgentConfigPanel` exactly as it exists today — no changes to that component or its test file.
- Import `render`/`screen`/`fireEvent`/`within` from `../test/render` (already established in this file), not `@testing-library/react` directly.

---

### Task 1: Add the collapsible global defaults panel to `SetupPage`

**Files:**
- Modify: `examples/web/frontend/src/routes/SetupPage.tsx`
- Modify: `examples/web/frontend/src/routes/SetupPage.test.tsx`

**Interfaces:**
- Consumes: `AgentConfigPanel` (unchanged, `{ label, config, onChange, envAvailable, providerPresets }`), `AgentConfigInput` type (unchanged, from `../api/types`), `emptyAgentConfig()` (already defined in this file).
- Produces: nothing new consumed by other files — `SetupPage` remains the sole consumer of this state.

- [ ] **Step 1: Write the failing tests**

The current baseline (verify yourself with `npm run test` from `examples/web/frontend/` before starting) is **86 passing tests**. `SetupPage.test.tsx` currently has 10 tests; these 3 new ones bring it to 13, for an expected total of **89** once this task is done.

In `examples/web/frontend/src/routes/SetupPage.test.tsx`, add these three tests immediately after the existing `it("falls back to the generic env var when a role-specific env var is unset", ...)` test (i.e., as the last three tests in the `describe("SetupPage", ...)` block, before its closing `});`):

```tsx
  it("shows a collapsible global defaults panel, collapsed by default", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));

    const globalControl = await screen.findByRole(
      "button", { name: "Set one configuration for all agents" },
    );
    expect(globalControl).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(globalControl);
    expect(globalControl).toHaveAttribute("aria-expanded", "true");
  });

  it("filling the global defaults panel and clicking Apply to all agents propagates it to every agent", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));

    const globalControl = await screen.findByRole(
      "button", { name: "Set one configuration for all agents" },
    );
    fireEvent.click(globalControl);
    const globalGroup = await screen.findByRole("group", { name: "Global defaults" });
    fireEvent.change(within(globalGroup).getByLabelText("API key"), { target: { value: "sk-global" } });
    fireEvent.change(within(globalGroup).getByLabelText("Model"), { target: { value: "gpt-4o-mini" } });
    fireEvent.click(screen.getByText("Apply to all agents"));

    const prosecutorControl = screen.getByRole("button", { name: /Prosecutor/ });
    fireEvent.click(prosecutorControl);
    const prosecutorGroup = await screen.findByRole("group", { name: "Prosecutor" });
    expect(within(prosecutorGroup).getByLabelText("API key")).toHaveValue("sk-global");
    expect(within(prosecutorGroup).getByLabelText("Model")).toHaveValue("gpt-4o-mini");

    const juror0Control = screen.getByRole("button", { name: /^Juror 0/ });
    fireEvent.click(juror0Control);
    const juror0Group = await screen.findByRole("group", { name: "Juror 0" });
    expect(within(juror0Group).getByLabelText("API key")).toHaveValue("sk-global");
  });

  it("a juror added after Apply to all agents was clicked starts blank", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));

    const globalControl = await screen.findByRole(
      "button", { name: "Set one configuration for all agents" },
    );
    fireEvent.click(globalControl);
    const globalGroup = await screen.findByRole("group", { name: "Global defaults" });
    fireEvent.change(within(globalGroup).getByLabelText("API key"), { target: { value: "sk-global" } });
    fireEvent.click(screen.getByText("Apply to all agents"));

    fireEvent.click(screen.getByText("Add juror"));
    const juror3Control = screen.getByRole("button", { name: /^Juror 3/ });
    fireEvent.click(juror3Control);
    const juror3Group = await screen.findByRole("group", { name: "Juror 3" });
    expect(within(juror3Group).getByLabelText("API key")).toHaveValue("");
  });
```

**A note on `aria-expanded`:** the first test asserts Mantine's `Accordion.Control` sets `aria-expanded` to reflect open/closed state. This is the standard ARIA disclosure-button pattern and Mantine's `Accordion.Control` is expected to implement it, but **verify this against the actual installed `@mantine/core` source** (e.g. `node_modules/@mantine/core/esm/components/Accordion/AccordionControl/AccordionControl.mjs`) before trusting it, the way every Mantine-behavior assumption in this codebase's history has been verified rather than assumed. If the real attribute name or mechanism differs, adjust the assertion to match reality while preserving the same intent (proving the panel starts collapsed and becomes expanded on click) — do not delete the test or weaken it to something that would pass regardless of collapse state.

**A note on `seed` preservation:** the spec requires "Apply to all agents" to preserve each juror's `seed` field (mirroring the existing per-juror `onChange` handler's `{ ...updated, seed: j.seed }` pattern). There is no test for this above, because `seed` is never exposed anywhere in this UI (`AgentConfigPanel` has no seed field, and `emptyJurorConfig()` never sets one) — there is nothing in the DOM to assert against. Implement the preservation in code per Step 3 below for correctness and consistency with the existing pattern; do not invent a fake DOM assertion to "cover" it.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd examples/web/frontend && npm run test -- src/routes/SetupPage.test.tsx`
Expected: the 3 new tests FAIL — there is no "Set one configuration for all agents" control yet, so `screen.findByRole("button", { name: "Set one configuration for all agents" })` will time out / throw.

- [ ] **Step 3: Implement the global defaults panel**

In `examples/web/frontend/src/routes/SetupPage.tsx`, add a new state declaration alongside the existing `prosecutor`/`defense`/`judge`/`jury` state (immediately after the `jury` state declaration):

```tsx
  const [globalConfig, setGlobalConfig] = useState<AgentConfigInput>(emptyAgentConfig());
```

Add a new handler function alongside `addJuror`/`removeJuror` (after `removeJuror`'s closing brace):

```tsx
  function applyGlobalConfigToAllAgents() {
    setProsecutor(globalConfig);
    setDefense(globalConfig);
    setJudge(globalConfig);
    setJury((current) => current.map((j) => ({ ...globalConfig, seed: j.seed })));
  }
```

In the JSX, inside the `<Stepper.Step label="Agents">` block, add a new `Accordion` immediately after the opening `<Stack gap="md" mt="md">` tag and immediately before the existing `<Accordion multiple defaultValue={[]}>`:

```tsx
            <Accordion>
              <Accordion.Item value="global-defaults">
                <Accordion.Control>Set one configuration for all agents</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <AgentConfigPanel
                      label="Global defaults" config={globalConfig} onChange={setGlobalConfig}
                      envAvailable={catalog.env_status.PSALM_API_KEY}
                      providerPresets={catalog.provider_presets}
                    />
                    <Button variant="light" onClick={applyGlobalConfigToAllAgents}>Apply to all agents</Button>
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
```

So the full `<Stepper.Step label="Agents">` block reads, in order: the new global-defaults `Accordion` above, then the existing per-agent `Accordion` (Prosecutor/Defense/Judge/jurors, unchanged), then the existing "Add juror" `Button` (unchanged).

No import changes are needed — `Accordion`, `Button`, `Stack` are already imported in this file (see the existing `import { Accordion, Badge, Button, Checkbox, Group, NativeSelect, NumberInput, Stack, Stepper, Text, Textarea, Title } from "@mantine/core";` at the top), and `AgentConfigPanel`/`AgentConfigInput`/`emptyAgentConfig` are already defined/imported in this file.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd examples/web/frontend && npm run test -- src/routes/SetupPage.test.tsx`
Expected: `13 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `89 passed` (86 baseline + 3 new); build succeeds with no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/SetupPage.tsx examples/web/frontend/src/routes/SetupPage.test.tsx
git commit -m "feat: add collapsible global agent defaults panel to SetupPage"
```

---
