# Courtroom Web Demo — Mantine Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the entire `examples/web/frontend` presentation layer on Mantine v7, applying the dark "Hybrid" theme and turning the Setup page into a 4-step wizard, without changing any backend, SDK, or frontend data-flow (reducer/store/API client) code.

**Architecture:** Every route/view/component file is rebuilt in place: same props, same data flow, new markup built from Mantine components wrapped in a `MantineProvider`/custom theme. Work proceeds bottom-up through the dependency graph (theme → leaf components → pages that compose them) so no task ever needs a component that doesn't exist yet.

**Tech Stack:** React 18, TypeScript (strict), Vite, Vitest + React Testing Library, `@mantine/core` + `@mantine/hooks` + `@mantine/form`, `@tabler/icons-react`.

## Global Constraints

- Mantine v7 (`@mantine/core@^7`, `@mantine/hooks@^7`, `@mantine/form@^7`), `@tabler/icons-react@^3`.
- Dark color scheme only — no light/dark toggle. Theme colors: page background `#14152a`, card/panel surface `#1e1f38`, secondary surface `#2a2b45`, primary/accent `#c9a83a`, accent glow `#d4a33a`. Verdict semantics use Mantine's default `green`/`red`/`gray` for Guilty/Not Guilty/Undecided.
- Component-selection principle: use Mantine's native-form-backed components (`TextInput`, `PasswordInput`, `NumberInput`, `Textarea`, `Checkbox`, `NativeSelect`, `Button`) wherever one fits, to keep existing `getByLabelText`/`fireEvent.change`/`getByRole("button")` test queries working with minimal changes. Use Mantine's real non-native components (`Tabs`, `Stepper`, `Accordion`, `Slider`, `Table`, `SegmentedControl`) where there's no native equivalent for the interaction being built; update that component's own tests to role/ARIA-based queries as part of the same task — `fireEvent.click` on the resulting real interactive elements (tabs, accordion controls, step labels) is sufficient for every interaction this plan's tests drive; none of them need a fuller synthetic-event sequence, so no `@testing-library/user-event` dependency is added.
- No toast/notification system. Errors stay as inline Mantine `Alert` components with `role="alert"` preserved (existing error-message test queries must keep working unchanged).
- `src/state/eventReducer.ts`, `src/state/store.ts`, `src/state/testFixtures.ts`, `src/api/client.ts`, `src/api/types.ts` are NOT modified by this plan — this is a rendering-only rebuild. No task should change these files' logic.
- Backend (`examples/web/backend/`) and the `psalm` SDK are entirely out of scope — no task touches them.
- Every frontend component/page test file is expected to require changes; that is expected scope for this plan, not a regression to avoid.

---

### Task 1: Install Mantine and fix the jsdom test environment

**Files:**
- Modify: `examples/web/frontend/package.json`
- Modify: `examples/web/frontend/src/test/setup.ts`
- Create: `examples/web/frontend/src/test/mantine-environment.test.tsx`

**Interfaces:**
- Produces: a working jsdom environment where any Mantine component can be rendered and tested. Every later task depends on this — none of Mantine's interactive components (`Select`, `Tabs`, `Stepper`, `Accordion`, `Slider`, etc.) render/behave correctly in jsdom without the mocks this task adds.

- [ ] **Step 1: Write the failing smoke test**

Create `examples/web/frontend/src/test/mantine-environment.test.tsx`:

```tsx
import { MantineProvider, Button } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("Mantine test environment", () => {
  it("renders a Mantine component without crashing", () => {
    render(
      <MantineProvider>
        <Button>Test</Button>
      </MantineProvider>,
    );
    expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"@mantine/core"` (not installed yet)

- [ ] **Step 3: Install Mantine and its peer packages**

Modify `examples/web/frontend/package.json` — add to `dependencies`:

```json
    "@mantine/core": "^7.17.0",
    "@mantine/form": "^7.17.0",
    "@mantine/hooks": "^7.17.0",
    "@tabler/icons-react": "^3.31.0",
```

(keep the existing `react`, `react-dom`, `react-router-dom`, `zustand` entries as they are, just add these four, keeping the object alphabetically sorted as it already is)

No `devDependencies` additions are needed — every interaction this plan's tests drive against Mantine's components (clicking a tab, an accordion control, a step label) works fine with the existing `fireEvent` from `@testing-library/react`.

Run: `cd examples/web/frontend && npm install`
Expected: installs cleanly, `package-lock.json` updates

- [ ] **Step 4: Run the test again to see the real failure**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — a runtime error from Mantine, something like `matchMedia is not a function` or a `ResizeObserver is not defined` error thrown during render (jsdom doesn't implement these browser APIs that Mantine's components rely on)

- [ ] **Step 5: Add the missing jsdom mocks**

Replace `examples/web/frontend/src/test/setup.ts` entirely:

```ts
import "@testing-library/jest-dom/vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverMock;

Element.prototype.getBoundingClientRect = () => ({
  width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0, x: 0, y: 0,
  toJSON: () => {},
});

Element.prototype.scrollIntoView = () => {};
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd examples/web/frontend && npm run test`
Expected: `77 passed` (76 existing + 1 new — the existing suite is unaffected since none of it uses Mantine yet)

- [ ] **Step 7: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 8: Commit**

```bash
git add examples/web/frontend/package.json examples/web/frontend/package-lock.json examples/web/frontend/src/test/setup.ts examples/web/frontend/src/test/mantine-environment.test.tsx
git commit -m "chore: install Mantine and fix jsdom test environment"
```

---

### Task 2: Theme, test-render helper, and the app shell

**Files:**
- Create: `examples/web/frontend/src/theme.ts`
- Create: `examples/web/frontend/src/test/render.tsx`
- Modify: `examples/web/frontend/src/main.tsx`
- Modify: `examples/web/frontend/src/App.tsx`
- Modify: `examples/web/frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: nothing from earlier tasks besides the working Mantine environment from Task 1.
- Produces:
  - `theme` — a `MantineThemeOverride` exported from `src/theme.ts`. Every later task that creates a test-rendering helper or references theme colors imports this.
  - `render` — a custom render function exported from `src/test/render.tsx`, re-exporting everything else from `@testing-library/react` (`screen`, `fireEvent`, `waitFor`, `within`, `act`, etc.) unchanged. It wraps its `ui` argument in `<MantineProvider theme={theme} forceColorScheme="dark">` before delegating to React Testing Library's own `render`. **Every task from here on replaces `import { render, screen, ... } from "@testing-library/react"` with an import from this helper** (relative path adjusted for the test file's directory depth) instead of wrapping each test's JSX in `MantineProvider` by hand.

- [ ] **Step 1: Write the failing test for App's new markup**

Modify `examples/web/frontend/src/App.test.tsx` — replace its contents:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "./api/client";
import App from "./App";
import { render, screen } from "./test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders the setup page at the root route", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      dimensions: [], presets: [], evaluation_strategies: [], provider_presets: [], env_status: {},
    });
    render(<App />);
    expect(await screen.findByText("New trial")).toBeInTheDocument();
  });

  it("navigates to History via the nav link", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      dimensions: [], presets: [], evaluation_strategies: [], provider_presets: [], env_status: {},
    });
    vi.spyOn(client, "listTrials").mockResolvedValue([]);
    render(<App />);
    await screen.findByText("New trial");
    screen.getByRole("link", { name: "History" }).click();
    expect(await screen.findByText("No trials run yet this session.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./test/render"` (doesn't exist yet)

- [ ] **Step 3: Write the theme**

Create `examples/web/frontend/src/theme.ts`:

```ts
import { createTheme, type MantineColorsTuple } from "@mantine/core";

const gold: MantineColorsTuple = [
  "#fdf7e6", "#f8ecc4", "#f2dfa0", "#ecd27a", "#e7c657",
  "#e2ba3e", "#d4a33a", "#c9a83a", "#a3862e", "#7d6423",
];

// Overrides Mantine's built-in "dark" palette so every component that uses
// the default dark-scheme surfaces (AppShell, Paper, Card, Modal, ...)
// picks up this app's navy palette automatically. Mantine's dark-scheme
// convention: shade 7 is the body background, shade 6 is the Paper/Card
// surface — indices chosen so those two land on the approved mockup's
// exact colors.
const dark: MantineColorsTuple = [
  "#d3d3e6", "#a7a7cb", "#8181af", "#606093", "#454577",
  "#2a2b45", "#1e1f38", "#14152a", "#101124", "#0b0c1c",
];

export const theme = createTheme({
  primaryColor: "gold",
  primaryShade: 6,
  colors: { gold, dark },
  defaultRadius: "md",
});
```

- [ ] **Step 4: Write the test-render helper**

Create `examples/web/frontend/src/test/render.tsx`:

```tsx
import { MantineProvider } from "@mantine/core";
import { render as rtlRender } from "@testing-library/react";
import type { ReactElement } from "react";
import { theme } from "../theme";

export function render(ui: ReactElement) {
  return rtlRender(
    <MantineProvider theme={theme} forceColorScheme="dark">{ui}</MantineProvider>,
  );
}

export * from "@testing-library/react";
```

- [ ] **Step 5: Wire up `MantineProvider` in `main.tsx`**

Replace `examples/web/frontend/src/main.tsx` entirely:

```tsx
import "@mantine/core/styles.css";
import { MantineProvider } from "@mantine/core";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { theme } from "./theme";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark" forceColorScheme="dark">
      <App />
    </MantineProvider>
  </React.StrictMode>,
);
```

- [ ] **Step 6: Rebuild `App.tsx` on `AppShell`**

Replace `examples/web/frontend/src/App.tsx` entirely:

```tsx
import { AppShell, Group, NavLink } from "@mantine/core";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import HistoryPage from "./routes/HistoryPage";
import LiveTrialPage from "./routes/LiveTrialPage";
import ResultsPage from "./routes/ResultsPage";
import SetupPage from "./routes/SetupPage";

function AppNav() {
  const location = useLocation();
  return (
    <Group h="100%" px="md" gap="xs">
      <NavLink
        component={Link} to="/" label="New trial"
        active={location.pathname === "/"} style={{ width: "auto" }}
      />
      <NavLink
        component={Link} to="/trials" label="History"
        active={location.pathname === "/trials"} style={{ width: "auto" }}
      />
    </Group>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell header={{ height: 56 }} padding="md">
        <AppShell.Header>
          <AppNav />
        </AppShell.Header>
        <AppShell.Main>
          <Routes>
            <Route path="/" element={<SetupPage />} />
            <Route path="/trial/:trialId" element={<LiveTrialPage />} />
            <Route path="/trial/:trialId/result" element={<ResultsPage />} />
            <Route path="/trials" element={<HistoryPage />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </BrowserRouter>
  );
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `78 passed` (77 from Task 1 + 1 net-new test in `App.test.tsx` — it had 1 test, now has 2). Every other existing test file still passes unmodified at this point — none of them render Mantine components yet, so they're unaffected by `App.tsx`'s rebuild.

- [ ] **Step 8: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 9: Commit**

```bash
git add examples/web/frontend/src/theme.ts examples/web/frontend/src/test/render.tsx examples/web/frontend/src/main.tsx examples/web/frontend/src/App.tsx examples/web/frontend/src/App.test.tsx
git commit -m "feat: add Mantine theme, test-render helper, and AppShell nav"
```

---

**A note on task structure from here on:** Tasks 3–11 rebuild an already-tested component in place, preserving its external contract (props, and — thanks to the native-backed-component principle — most test queries). Classic red-green TDD doesn't map cleanly onto "rebuild with preserved behavior," so these tasks instead use the test suite as a safety net: update the test file first (confirming it still describes the right behavior against the OLD component), then rebuild the component, then confirm the SAME tests still pass against the NEW one. Where a task adds genuinely new behavior (e.g. StageView's update-pulse), that gets a real new failing-then-passing test.

### Task 3: Rebuild `AgentConfigPanel`

**Files:**
- Modify: `examples/web/frontend/src/components/AgentConfigPanel.tsx`
- Modify: `examples/web/frontend/src/components/AgentConfigPanel.test.tsx`

**Interfaces:**
- Consumes: `render`, `screen`, `fireEvent` from `../test/render` (Task 2).
- Produces: unchanged — same default export, same `AgentConfigPanelProps` shape (`label`, `config`, `onChange`, `envAvailable`, `providerPresets`). `SetupPage` (Task 9) renders 6 instances of this component inside `Accordion.Item`s.

- [ ] **Step 1: Update the test file to use the shared render helper**

Replace `examples/web/frontend/src/components/AgentConfigPanel.test.tsx` entirely:

```tsx
import { describe, expect, it, vi } from "vitest";
import AgentConfigPanel from "./AgentConfigPanel";
import { fireEvent, render, screen } from "../test/render";

const providerPresets = [{ id: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1" }];

describe("AgentConfigPanel", () => {
  it("calls onChange when the API key field changes", () => {
    const onChange = vi.fn();
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={onChange} envAvailable={false} providerPresets={providerPresets} />,
    );
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    expect(onChange).toHaveBeenCalledWith({ api_key: "sk-test" });
  });

  it("shows an env-var placeholder on the API key field when available", () => {
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={vi.fn()} envAvailable providerPresets={providerPresets} />,
    );
    expect(screen.getByLabelText("API key")).toHaveAttribute("placeholder", "✓ using environment variable");
  });

  it("shows a required placeholder on the API key field when no env var is available", () => {
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={vi.fn()} envAvailable={false} providerPresets={providerPresets} />,
    );
    expect(screen.getByLabelText("API key")).toHaveAttribute("placeholder", "required");
  });

  it("applying a provider preset fills the base URL", () => {
    const onChange = vi.fn();
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={onChange} envAvailable={false} providerPresets={providerPresets} />,
    );
    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "openai" } });
    expect(onChange).toHaveBeenCalledWith({ base_url: "https://api.openai.com/v1" });
  });

  it("updating the temperature field parses it as a number", () => {
    const onChange = vi.fn();
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={onChange} envAvailable={false} providerPresets={providerPresets} />,
    );
    fireEvent.change(screen.getByLabelText("Temperature"), { target: { value: "0.7" } });
    expect(onChange).toHaveBeenCalledWith({ temperature: 0.7 });
  });

  it("is reachable as an accessible group named after its label", () => {
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={vi.fn()} envAvailable={false} providerPresets={providerPresets} />,
    );
    expect(screen.getByRole("group", { name: "Prosecutor" })).toBeInTheDocument();
  });
});
```

(the temperature and accessible-group tests are new — the first four are the pre-existing tests, unchanged except the import source)

- [ ] **Step 2: Run the tests against the current (pre-Mantine) component**

Run: `cd examples/web/frontend && npm run test -- src/components/AgentConfigPanel.test.tsx`
Expected: 4 of 6 pass (the four pre-existing assertions still hold against the current plain-HTML component); the 2 new tests FAIL — the temperature test fails because the current handler is fine, so check its actual failure is just from the import (should pass) — **actually expect all 6 to fail** if the import `"../test/render"` doesn't exist yet from a previous incomplete task; since Task 2 already created it, expect 6 pass, EXCEPT this doesn't yet prove the Mantine rebuild is needed. Instead: expect all 6 to PASS at this point, since the current native-HTML component already satisfies every assertion including the new ones (native `<input type="number">` and native `<fieldset>`/`<legend>` already behave this way). This step exists to confirm the test file itself is valid before the rebuild — not to observe a failure.

- [ ] **Step 3: Rebuild the component on Mantine**

Replace `examples/web/frontend/src/components/AgentConfigPanel.tsx` entirely:

```tsx
import { Fieldset, NativeSelect, NumberInput, PasswordInput, Stack, TextInput } from "@mantine/core";
import type { AgentConfigInput, ProviderPreset } from "../api/types";

interface AgentConfigPanelProps {
  label: string;
  config: AgentConfigInput;
  onChange: (config: AgentConfigInput) => void;
  envAvailable: boolean;
  providerPresets: ProviderPreset[];
}

export default function AgentConfigPanel(
  { label, config, onChange, envAvailable, providerPresets }: AgentConfigPanelProps,
) {
  function applyProviderPreset(id: string) {
    const preset = providerPresets.find((p) => p.id === id);
    if (!preset) return;
    onChange({ ...config, base_url: preset.base_url });
  }

  const inputId = label.toLowerCase().replace(/\s+/g, "-");
  const requiredOrEnv = envAvailable ? "✓ using environment variable" : "required";
  const envOrRequired = envAvailable ? "leave blank to use environment variable" : "required";

  return (
    <Fieldset legend={label}>
      <Stack gap="sm">
        <NativeSelect
          id={`${inputId}-provider`}
          label="Provider"
          placeholder="Choose a provider (optional)"
          data={providerPresets.map((p) => ({ value: p.id, label: p.label }))}
          onChange={(e) => applyProviderPreset(e.target.value)}
        />
        <TextInput
          id={`${inputId}-base-url`}
          label="Base URL"
          value={config.base_url ?? ""}
          onChange={(e) => onChange({ ...config, base_url: e.target.value })}
          placeholder={envOrRequired}
        />
        <PasswordInput
          id={`${inputId}-api-key`}
          label="API key"
          value={config.api_key ?? ""}
          onChange={(e) => onChange({ ...config, api_key: e.target.value })}
          placeholder={requiredOrEnv}
        />
        <TextInput
          id={`${inputId}-model`}
          label="Model"
          value={config.model ?? ""}
          onChange={(e) => onChange({ ...config, model: e.target.value })}
          placeholder={envOrRequired}
        />
        <NumberInput
          id={`${inputId}-temperature`}
          label="Temperature"
          step={0.1}
          min={0}
          max={2}
          value={config.temperature ?? ""}
          onChange={(value) => onChange({
            ...config, temperature: value === "" ? undefined : Number(value),
          })}
        />
      </Stack>
    </Fieldset>
  );
}
```

Mantine's `Fieldset` renders a real `<fieldset>` with the `legend` prop as a real `<legend>`, so the accessible group name is derived natively — no explicit `aria-label` needed. `NativeSelect`, `TextInput`, and `PasswordInput` all render real underlying `<select>`/`<input>` elements associated with their `label` via `id`/`htmlFor`, so `getByLabelText` and `fireEvent.change` keep working unchanged. `NumberInput` also drives its underlying text input via native change events internally, so `fireEvent.change` on it works the same way too.

- [ ] **Step 4: Run the tests to verify they still pass**

Run: `cd examples/web/frontend && npm run test -- src/components/AgentConfigPanel.test.tsx`
Expected: `6 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `80 passed` (78 from Task 2 + 2 new in this file); build succeeds with no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/components/AgentConfigPanel.tsx examples/web/frontend/src/components/AgentConfigPanel.test.tsx
git commit -m "feat: rebuild AgentConfigPanel on Mantine"
```

---

### Task 4: Rebuild `StageView`, with a new update-pulse cue

**Files:**
- Modify: `examples/web/frontend/src/views/StageView.tsx`
- Modify: `examples/web/frontend/src/views/StageView.test.tsx`
- Modify: `examples/web/frontend/src/index.css`

**Interfaces:**
- Consumes: `DimensionState` (unchanged, from `../state/eventReducer`), `render`/`screen` from `../test/render` (Task 2).
- Produces: unchanged default export signature (`{ dimension: DimensionState | null }`) and the still-exported `phaseLabel(dimension: DimensionState): string` helper — `LiveTrialPage` (Task 7) and `ResultsPage` (Task 10) both import `phaseLabel` from this file.

- [ ] **Step 1: Update the test file — preserve existing assertions, add the new pulse test**

Replace `examples/web/frontend/src/views/StageView.test.tsx` entirely:

```tsx
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import StageView from "./StageView";
import { render, screen } from "../test/render";

describe("StageView", () => {
  it("shows a waiting message with no dimension selected", () => {
    render(<StageView dimension={null} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();
  });

  it("shows the current phase and round", () => {
    render(<StageView dimension={makeDimensionState({ phase: "argumentation", currentRound: 2 })} />);
    expect(screen.getByText(/Argumentation — round 2/)).toBeInTheDocument();
  });

  it("shows the prosecutor's speech bubble when they are speaking", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "prosecution", latestSpeech: "The scar matches." })} />,
    );
    expect(screen.getByText('"The scar matches."')).toBeInTheDocument();
  });

  it("shows a juror's speech bubble in the jury area when they are speaking", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "juror-1", latestSpeech: "I believe the evidence is clear." })} />,
    );
    const jury = screen.getByTestId("stage-jury");
    expect(jury.textContent).toContain("I believe the evidence is clear.");
  });

  it("does not show a speech bubble for the side that is not currently speaking", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "prosecution", latestSpeech: "The scar matches." })} />,
    );
    const defensePodium = screen.getByTestId("stage-podium-defense");
    expect(defensePodium.textContent).not.toContain("The scar matches.");
  });

  it("tallies juror votes", () => {
    const dimension = makeDimensionState({
      jurorVotes: {
        "juror-0": { vote: "Guilty", rationale: "r", dimensionScores: [] },
        "juror-1": { vote: "Guilty", rationale: "r", dimensionScores: [] },
        "juror-2": { vote: "Not Guilty", rationale: "r", dimensionScores: [] },
      },
    });
    render(<StageView dimension={dimension} />);
    expect(screen.getByText("2 × Guilty")).toBeInTheDocument();
    expect(screen.getByText("1 × Not Guilty")).toBeInTheDocument();
  });

  it("shows the verdict once reached", () => {
    render(<StageView dimension={makeDimensionState({ phase: "verdict", verdict: "Guilty" })} />);
    expect(screen.getByText("Verdict: Guilty")).toBeInTheDocument();
  });

  it("applies a pulse-highlight class to newly-arrived speech so updates are visually obvious", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "prosecution", latestSpeech: "The scar matches." })} />,
    );
    expect(screen.getByText('"The scar matches."')).toHaveClass("stage-speech-pulse");
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/views/StageView.test.tsx`
Expected: 7 pass, 1 FAILS — `applies a pulse-highlight class...` fails because `stage-speech-pulse` isn't a class the current component ever applies

- [ ] **Step 3: Add the pulse keyframe to `index.css`**

Modify `examples/web/frontend/src/index.css` — append to the end of the file:

```css

@keyframes stage-speech-pulse {
  from { background-color: rgba(201, 168, 58, 0.35); }
  to { background-color: transparent; }
}

.stage-speech-pulse {
  animation: stage-speech-pulse 900ms ease-out;
  border-radius: 4px;
  padding: 2px 6px;
}
```

- [ ] **Step 4: Rebuild the component on Mantine**

Replace `examples/web/frontend/src/views/StageView.tsx` entirely:

```tsx
import { useMemo } from "react";
import { Badge, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconScale } from "@tabler/icons-react";
import type { DimensionState } from "../state/eventReducer";

interface StageViewProps {
  dimension: DimensionState | null;
}

export function phaseLabel(dimension: DimensionState): string {
  if (dimension.phase === "verdict") return `Verdict: ${dimension.verdict}`;
  if (dimension.phase === "deliberation") return `Deliberation — round ${dimension.currentRound}`;
  return `Argumentation — round ${dimension.currentRound}`;
}

const SPEAKING_STYLE = {
  borderColor: "var(--mantine-color-gold-6)",
  boxShadow: "0 0 12px var(--mantine-color-gold-6)",
};

export default function StageView({ dimension }: StageViewProps) {
  if (dimension === null) {
    return <Text c="dimmed" className="stage-empty">Waiting for the trial to begin...</Text>;
  }

  const voteCounts = useMemo(() => Object.values(dimension.jurorVotes).reduce<Record<string, number>>((acc, v) => {
    acc[v.vote] = (acc[v.vote] ?? 0) + 1;
    return acc;
  }, {}), [dimension.jurorVotes]);

  const isJurorSpeaking = dimension.speakingRole !== null
    && dimension.speakingRole !== "prosecution"
    && dimension.speakingRole !== "defense";

  function badgeColor(vote: string): string {
    if (vote === "Guilty") return "red";
    if (vote === "Not Guilty") return "green";
    return "gray";
  }

  return (
    <Stack gap="md" className="stage-view">
      <Title order={4} className="stage-phase-indicator">{phaseLabel(dimension)}</Title>

      <Card withBorder padding="md" data-testid="stage-bench">
        <Group gap="xs">
          <IconScale size={18} />
          <Text fw={600}>Judge</Text>
        </Group>
        {dimension.rejectedArgumentCount > 0 && (
          <Text size="sm" c="dimmed">{dimension.rejectedArgumentCount} objection(s) sustained so far.</Text>
        )}
      </Card>

      <Group grow gap="md">
        <Card
          withBorder padding="md" data-testid="stage-podium-prosecution"
          style={dimension.speakingRole === "prosecution" ? SPEAKING_STYLE : undefined}
        >
          <Text fw={600} size="sm" tt="uppercase" c="dimmed">Prosecutor</Text>
          {dimension.speakingRole === "prosecution" && dimension.latestSpeech && (
            <Text key={dimension.latestSpeech} className="stage-speech stage-speech-pulse" mt="xs">
              &quot;{dimension.latestSpeech}&quot;
            </Text>
          )}
        </Card>
        <Card
          withBorder padding="md" data-testid="stage-podium-defense"
          style={dimension.speakingRole === "defense" ? SPEAKING_STYLE : undefined}
        >
          <Text fw={600} size="sm" tt="uppercase" c="dimmed">Defense</Text>
          {dimension.speakingRole === "defense" && dimension.latestSpeech && (
            <Text key={dimension.latestSpeech} className="stage-speech stage-speech-pulse" mt="xs">
              &quot;{dimension.latestSpeech}&quot;
            </Text>
          )}
        </Card>
      </Group>

      <Card withBorder padding="md" data-testid="stage-jury">
        <Text fw={600} size="sm">Jury ({Object.keys(dimension.jurorVotes).length} voted)</Text>
        <Group gap="xs" mt="xs">
          {Object.entries(voteCounts).map(([vote, count]) => (
            <Badge key={vote} color={badgeColor(vote)} variant="light">{count} × {vote}</Badge>
          ))}
        </Group>
        {isJurorSpeaking && dimension.latestSpeech && (
          <Text key={dimension.latestSpeech} className="stage-speech stage-speech-pulse" mt="xs">
            {dimension.speakingRole}: &quot;{dimension.latestSpeech}&quot;
          </Text>
        )}
      </Card>
    </Stack>
  );
}
```

The `key={dimension.latestSpeech}` on each speech `Text` is what makes the pulse re-trigger on every new line of dialogue: React treats a changed `key` as "a different element," unmounting the old one and mounting a fresh one — which restarts the `stage-speech-pulse` CSS animation from its `from` state every time, even if the surrounding `Card` itself doesn't remount.

- [ ] **Step 5: Run the tests to verify they all pass**

Run: `cd examples/web/frontend && npm run test -- src/views/StageView.test.tsx`
Expected: `8 passed`

- [ ] **Step 6: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `81 passed` (80 from Task 3 + 1 new in this file); build succeeds

- [ ] **Step 7: Commit**

```bash
git add examples/web/frontend/src/views/StageView.tsx examples/web/frontend/src/views/StageView.test.tsx examples/web/frontend/src/index.css
git commit -m "feat: rebuild StageView on Mantine with an update-pulse cue"
```

---

### Task 5: Rebuild `TranscriptView` on Mantine's `Timeline`, add auto-scroll

**Files:**
- Modify: `examples/web/frontend/src/views/TranscriptView.tsx`
- Modify: `examples/web/frontend/src/views/TranscriptView.test.tsx`

**Interfaces:**
- Consumes: `DimensionState`/`TranscriptEntry`/`mergeTranscript` (unchanged), `render`/`screen` from `../test/render` (Task 2).
- Produces: unchanged default export signature (`{ dimension: DimensionState | null; sharedTranscript: TranscriptEntry[] }`) — consumed by `LiveTrialPage` (Task 7) and `TimelineView`'s sibling usage pattern (Task 6 does not import this file, but both are consumed identically by `LiveTrialPage`).

- [ ] **Step 1: Update the test file — preserve existing assertions, add an auto-scroll test**

Replace `examples/web/frontend/src/views/TranscriptView.test.tsx` entirely:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TranscriptView from "./TranscriptView";
import { render, screen } from "../test/render";

function withSequence(sequence: number): PSALMEvent {
  return { sequence } as PSALMEvent;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TranscriptView", () => {
  it("shows a waiting message when there are no entries yet", () => {
    render(<TranscriptView dimension={null} sharedTranscript={[]} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();
  });

  it("renders each transcript entry's text", () => {
    const dimension = makeDimensionState({
      transcript: [
        { id: "1", timestamp: "t", dimension: "Character", kind: "argument", role: "prosecution", text: "The scar matches.", raw: withSequence(1) },
        { id: "2", timestamp: "t", dimension: "Character", kind: "rejection", role: "prosecution", text: "Judge sustains an objection.", raw: withSequence(2) },
      ],
    });
    render(<TranscriptView dimension={dimension} sharedTranscript={[]} />);
    expect(screen.getByText("The scar matches.")).toBeInTheDocument();
    expect(screen.getByText("Judge sustains an objection.")).toBeInTheDocument();
  });

  it("merges and orders shared and dimension transcripts by sequence", () => {
    const shared = [
      { id: "s1", timestamp: "t", dimension: null, kind: "argument", text: "Shared first.", raw: withSequence(1) },
    ];
    const dimension = makeDimensionState({
      transcript: [
        { id: "d1", timestamp: "t", dimension: "Character", kind: "vote", text: "Then a vote.", raw: withSequence(2) },
      ],
    });
    render(<TranscriptView dimension={dimension} sharedTranscript={shared} />);
    const entries = screen.getAllByTestId("transcript-entry");
    expect(entries.map((el) => el.textContent)).toEqual(["Shared first.", "Then a vote."]);
  });

  it("auto-scrolls to the newest entry when new entries arrive", () => {
    const scrollIntoViewSpy = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    const dimension = makeDimensionState({
      transcript: [
        { id: "1", timestamp: "t", dimension: "Character", kind: "argument", role: "prosecution", text: "First.", raw: withSequence(1) },
      ],
    });
    render(<TranscriptView dimension={dimension} sharedTranscript={[]} />);
    expect(scrollIntoViewSpy).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/views/TranscriptView.test.tsx`
Expected: 3 pass, 1 FAILS — the auto-scroll test fails because the current component never calls `scrollIntoView`

- [ ] **Step 3: Rebuild the component on Mantine's `Timeline`, with auto-scroll**

Replace `examples/web/frontend/src/views/TranscriptView.tsx` entirely:

```tsx
import { useEffect, useMemo, useRef } from "react";
import { Text, Timeline } from "@mantine/core";
import type { DimensionState, TranscriptEntry } from "../state/eventReducer";
import { mergeTranscript } from "../state/eventReducer";

interface TranscriptViewProps {
  dimension: DimensionState | null;
  sharedTranscript: TranscriptEntry[];
}

const ROLE_COLORS: Record<string, string> = {
  prosecution: "orange",
  defense: "blue",
};

function entryColor(entry: TranscriptEntry): string {
  if (["rejection", "validation", "consensus", "stability_check"].includes(entry.kind)) {
    return "grape";
  }
  if (entry.role && ROLE_COLORS[entry.role]) return ROLE_COLORS[entry.role];
  return "gray";
}

export default function TranscriptView({ dimension, sharedTranscript }: TranscriptViewProps) {
  const entries = useMemo(
    () => mergeTranscript(sharedTranscript, dimension),
    [sharedTranscript, dimension],
  );
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries.length]);

  if (entries.length === 0) {
    return <Text c="dimmed" className="transcript-empty">Waiting for the trial to begin...</Text>;
  }

  return (
    <div className="transcript-view" aria-live="polite" style={{ maxHeight: 480, overflowY: "auto" }}>
      <Timeline active={entries.length} bulletSize={14} lineWidth={2}>
        {entries.map((entry) => (
          <Timeline.Item key={entry.id} data-testid="transcript-entry" color={entryColor(entry)}>
            <Text size="sm">{entry.text}</Text>
          </Timeline.Item>
        ))}
      </Timeline>
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they all pass**

Run: `cd examples/web/frontend && npm run test -- src/views/TranscriptView.test.tsx`
Expected: `4 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `82 passed` (81 from Task 4 + 1 new in this file); build succeeds

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/views/TranscriptView.tsx examples/web/frontend/src/views/TranscriptView.test.tsx
git commit -m "feat: rebuild TranscriptView on Mantine Timeline with auto-scroll"
```

---

### Task 6: Rebuild `TimelineView` on Mantine's `Stepper`

**Files:**
- Modify: `examples/web/frontend/src/views/TimelineView.tsx`
- Modify: `examples/web/frontend/src/views/TimelineView.test.tsx`

**Interfaces:**
- Consumes: `DimensionState`/`TranscriptEntry`/`mergeTranscript` (unchanged), `render`/`screen` from `../test/render` (Task 2).
- Produces: unchanged default export signature (`{ dimension: DimensionState | null; sharedTranscript: TranscriptEntry[] }`) — consumed by `LiveTrialPage` (Task 7).

**A note on this task's test rewrite:** the current component renders each step's status as a literal text prefix (`✅`/`▶`/`○`). Mantine's `Stepper` renders its own built-in icons for completed/active/upcoming steps — it does not support arbitrary text prefixes — so the old `getByText(/▶ Argumentation round 2/)` assertions no longer make sense against the new markup. Each `Stepper.Step` gets an explicit `data-status` attribute carrying the same `"done" | "current" | "upcoming"` value the component already computes, and tests assert against that instead of a rendered icon glyph — this is the "adopt the real component, rewrite its tests to real semantics" case described in the Global Constraints.

- [ ] **Step 1: Rewrite the test file against the new `data-status` contract**

Replace `examples/web/frontend/src/views/TimelineView.test.tsx` entirely:

```tsx
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TimelineView from "./TimelineView";
import { render, screen } from "../test/render";

function withSequence(sequence: number): PSALMEvent {
  return { sequence } as PSALMEvent;
}

describe("TimelineView", () => {
  it("shows a waiting message with no dimension selected", () => {
    render(<TimelineView dimension={null} sharedTranscript={[]} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();
  });

  it("marks the current argumentation round as current and earlier rounds as done", () => {
    render(<TimelineView dimension={makeDimensionState({ phase: "argumentation", currentRound: 2 })} sharedTranscript={[]} />);
    // Steps are: 0 Setup, 1 Argumentation round 1, 2 Argumentation round 2, 3 Deliberation, 4 Verdict.
    expect(screen.getByTestId("timeline-step-2")).toHaveAttribute("data-status", "current");
    expect(screen.getByTestId("timeline-step-2")).toHaveTextContent("Argumentation round 2");
    expect(screen.getByTestId("timeline-step-1")).toHaveAttribute("data-status", "done");
    expect(screen.getByTestId("timeline-step-1")).toHaveTextContent("Argumentation round 1");
  });

  it("marks verdict as done once reached", () => {
    render(<TimelineView dimension={makeDimensionState({ phase: "verdict", currentRound: 2 })} sharedTranscript={[]} />);
    expect(screen.getByTestId("timeline-step-4")).toHaveAttribute("data-status", "done");
    expect(screen.getByTestId("timeline-step-4")).toHaveTextContent("Verdict");
  });

  it("renders the merged transcript for the current phase", () => {
    const dimension = makeDimensionState({
      transcript: [
        { id: "1", timestamp: "t", dimension: "Character", kind: "argument", text: "The scar matches.", raw: withSequence(1) },
      ],
    });
    render(<TimelineView dimension={dimension} sharedTranscript={[]} />);
    expect(screen.getByText("The scar matches.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/views/TimelineView.test.tsx`
Expected: FAIL — `getByTestId("timeline-step-2")` etc. don't exist yet on the current component

- [ ] **Step 3: Rebuild the component on Mantine's `Stepper`**

Replace `examples/web/frontend/src/views/TimelineView.tsx` entirely:

```tsx
import { Stack, Stepper, Text } from "@mantine/core";
import type { DimensionState, TranscriptEntry } from "../state/eventReducer";
import { mergeTranscript } from "../state/eventReducer";

interface TimelineViewProps {
  dimension: DimensionState | null;
  sharedTranscript: TranscriptEntry[];
}

interface StepInfo {
  label: string;
  status: "done" | "current" | "upcoming";
}

function buildSteps(dimension: DimensionState): StepInfo[] {
  const steps: StepInfo[] = [{ label: "Setup", status: "done" }];
  const maxKnownRound = Math.max(dimension.currentRound, 1);
  for (let round = 1; round <= maxKnownRound; round++) {
    let status: StepInfo["status"] = "done";
    if (dimension.phase === "argumentation" && round === dimension.currentRound) status = "current";
    if (round > dimension.currentRound) status = "upcoming";
    steps.push({ label: `Argumentation round ${round}`, status });
  }
  steps.push({
    label: "Deliberation",
    status: dimension.phase === "deliberation" ? "current" : dimension.phase === "verdict" ? "done" : "upcoming",
  });
  steps.push({ label: "Verdict", status: dimension.phase === "verdict" ? "done" : "upcoming" });
  return steps;
}

export default function TimelineView({ dimension, sharedTranscript }: TimelineViewProps) {
  if (dimension === null) {
    return <Text c="dimmed" className="timeline-empty">Waiting for the trial to begin...</Text>;
  }

  const steps = buildSteps(dimension);
  const currentIndex = steps.findIndex((s) => s.status === "current");
  const activeIndex = currentIndex === -1 ? steps.length : currentIndex;
  const entries = mergeTranscript(sharedTranscript, dimension);

  return (
    <Stack gap="lg" className="timeline-view">
      <Stepper active={activeIndex} orientation="vertical" size="sm" iconSize={22}>
        {steps.map((step, index) => (
          <Stepper.Step
            key={step.label} label={step.label}
            data-testid={`timeline-step-${index}`} data-status={step.status}
          />
        ))}
      </Stepper>
      <Stack gap="xs" className="timeline-transcript">
        {entries.map((entry) => (
          <Text key={entry.id} size="sm">{entry.text}</Text>
        ))}
      </Stack>
    </Stack>
  );
}
```

- [ ] **Step 4: Run the tests to verify they all pass**

Run: `cd examples/web/frontend && npm run test -- src/views/TimelineView.test.tsx`
Expected: `4 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `82 passed` (unchanged from Task 5 — this file still has exactly 4 tests, just rewritten, not added to); build succeeds

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/views/TimelineView.tsx examples/web/frontend/src/views/TimelineView.test.tsx
git commit -m "feat: rebuild TimelineView on Mantine Stepper"
```

---

### Task 7: Rebuild `LiveTrialPage` on Mantine `Tabs`, `SegmentedControl`, and `Badge`

**Files:**
- Modify: `examples/web/frontend/src/routes/LiveTrialPage.tsx`
- Modify: `examples/web/frontend/src/routes/LiveTrialPage.test.tsx`

**Interfaces:**
- Consumes: `StageView`/`phaseLabel` (Task 4), `TranscriptView` (Task 5), `TimelineView` (Task 6), `useTrialStore` (unchanged), `render`/`screen`/`act` from `../test/render` (Task 2).
- Produces: unchanged default export (`LiveTrialPage(): JSX.Element`, no props, reads `trialId` from the route).

**A note on this task's test rewrite:** four tests assert `getByText("Stage")).toHaveClass("active")` or `getByRole("button", { name: "Character" })` — both assumptions about the OLD plain-`<button>` markup. Mantine's `Tabs.Tab` renders a real ARIA `role="tab"` with `aria-selected` reflecting which tab is active (not a literal `"active"` class), and Mantine's `SegmentedControl` renders each option as a `role="radio"` input under the hood (not a `<button>`). These four tests are rewritten to the correct ARIA-based queries; the other three (start-stream, status-strip, navigate-on-done) are unaffected by the markup change and only get the import-source swap.

- [ ] **Step 1: Rewrite the test file against the new markup**

Replace `examples/web/frontend/src/routes/LiveTrialPage.test.tsx` entirely:

```tsx
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { PSALMEvent } from "../api/types";
import { useTrialStore } from "../state/store";
import LiveTrialPage from "./LiveTrialPage";
import { act, render, screen } from "../test/render";

function renderAtTrial(trialId: string) {
  return render(
    <MemoryRouter initialEntries={[`/trial/${trialId}`]}>
      <Routes>
        <Route path="/trial/:trialId" element={<LiveTrialPage />} />
        <Route path="/trial/:trialId/result" element={<div>RESULT PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LiveTrialPage", () => {
  beforeEach(() => {
    useTrialStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts a live stream for the trial id in the URL", () => {
    const openSpy = vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    expect(openSpy).toHaveBeenCalledWith("abc123", expect.any(Function), expect.any(Function));
  });

  it("defaults to the Stage view", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    expect(screen.getByRole("tab", { name: "Stage" })).toHaveAttribute("aria-selected", "true");
  });

  it("switching tabs changes the active view", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    act(() => {
      screen.getByRole("tab", { name: "Transcript" }).click();
    });
    expect(screen.getByRole("tab", { name: "Transcript" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows a dimension selector only once 2+ dimensions are running", () => {
    let onEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, cb) => {
      onEvent = cb;
      return () => {};
    });
    renderAtTrial("abc123");
    expect(screen.queryByRole("radio", { name: "Character" })).not.toBeInTheDocument();

    act(() => {
      onEvent?.({
        event_id: "1", sequence: 1, timestamp: "t", run_id: "r", dimension: "Character",
        category: "lifecycle", type: "dimension_started", dimension_type: "infringement", importance: "high",
      } as PSALMEvent);
      onEvent?.({
        event_id: "2", sequence: 2, timestamp: "t", run_id: "r", dimension: "Plot",
        category: "lifecycle", type: "dimension_started", dimension_type: "infringement", importance: "high",
      } as PSALMEvent);
    });

    expect(screen.getByRole("radio", { name: "Character" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Plot" })).toBeInTheDocument();
  });

  it("shows a status strip with the OTHER dimensions' phase/round while one is selected", () => {
    let onEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, cb) => {
      onEvent = cb;
      return () => {};
    });
    renderAtTrial("abc123");

    act(() => {
      onEvent?.({
        event_id: "1", sequence: 1, timestamp: "t", run_id: "r", dimension: "Character",
        category: "lifecycle", type: "dimension_started", dimension_type: "infringement", importance: "high",
      } as PSALMEvent);
      onEvent?.({
        event_id: "2", sequence: 2, timestamp: "t", run_id: "r", dimension: "Plot",
        category: "lifecycle", type: "dimension_started", dimension_type: "infringement", importance: "high",
      } as PSALMEvent);
      onEvent?.({
        event_id: "3", sequence: 3, timestamp: "t", run_id: "r", dimension: "Plot",
        category: "argumentation", type: "argumentation_round_started", round: 2,
      } as PSALMEvent);
    });

    const strip = screen.getByTestId("dimension-status-strip");
    expect(strip.textContent).toContain("Plot");
    expect(strip.textContent).toContain("round 2");
    expect(strip.textContent).not.toContain("Character:");
  });

  it("navigates to the results page once the trial is done", async () => {
    let onEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, cb) => {
      onEvent = cb;
      return () => {};
    });
    renderAtTrial("abc123");

    act(() => {
      onEvent?.({
        event_id: "1", sequence: 1, timestamp: "t", run_id: "r", dimension: null,
        category: "verdict", type: "final_verdict_reached",
        result: {
          verdict: "Guilty", rationale: "r", dimension_verdicts: [],
          metadata: {
            duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
            voting_strategy_applied: "unanimous", agent_failures: [],
          },
        },
      } as PSALMEvent);
    });

    expect(await screen.findByText("RESULT PAGE")).toBeInTheDocument();
  });

  it("does not immediately navigate using stale status left over from a previous trial", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    useTrialStore.setState((s) => ({
      ...s,
      state: { ...s.state, status: "done" },
    }));
    renderAtTrial("newTrialId");
    expect(screen.getByRole("tab", { name: "Stage" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("RESULT PAGE")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/routes/LiveTrialPage.test.tsx`
Expected: 3 pass (start-stream, status-strip, navigate-on-done), 4 FAIL (the `role="tab"`/`role="radio"` queries find nothing against the current plain-`<button>` markup)

- [ ] **Step 3: Rebuild the component on Mantine**

Replace `examples/web/frontend/src/routes/LiveTrialPage.tsx` entirely:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Group, SegmentedControl, Stack, Tabs, Title } from "@mantine/core";
import { useTrialStore } from "../state/store";
import StageView, { phaseLabel } from "../views/StageView";
import TimelineView from "../views/TimelineView";
import TranscriptView from "../views/TranscriptView";

type ViewName = "stage" | "transcript" | "timeline";

const VIEW_LABELS: Record<ViewName, string> = {
  stage: "Stage", transcript: "Transcript", timeline: "Timeline",
};

export default function LiveTrialPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const navigate = useNavigate();
  const trialState = useTrialStore((s) => s.state);
  const startLive = useTrialStore((s) => s.startLive);
  const [activeView, setActiveView] = useState<ViewName>("stage");
  const [selectedDimension, setSelectedDimension] = useState<string | null>(null);

  useEffect(() => {
    if (trialId) startLive(trialId);
  }, [trialId, startLive]);

  useEffect(() => {
    const currentStatus = useTrialStore.getState().state.status;
    if ((currentStatus === "done" || currentStatus === "error") && trialId) {
      navigate(`/trial/${trialId}/result`);
    }
  }, [trialState.status, trialId, navigate]);

  useEffect(() => {
    if (!selectedDimension && trialState.dimensionOrder.length > 0) {
      setSelectedDimension(trialState.dimensionOrder[0]);
    }
  }, [trialState.dimensionOrder, selectedDimension]);

  const dimension = selectedDimension ? trialState.dimensions[selectedDimension] ?? null : null;

  return (
    <Stack gap="md" className="live-trial-page">
      <Title order={2}>Trial in progress</Title>

      {trialState.dimensionOrder.length > 1 && (
        <SegmentedControl
          data={trialState.dimensionOrder.map((name) => ({ label: name, value: name }))}
          value={selectedDimension ?? ""}
          onChange={setSelectedDimension}
        />
      )}

      {trialState.dimensionOrder.length > 1 && (
        <Group gap="xs" data-testid="dimension-status-strip">
          {trialState.dimensionOrder
            .filter((name) => name !== selectedDimension)
            .map((name) => (
              <Badge key={name} variant="light" color="gray">
                {name}: {phaseLabel(trialState.dimensions[name])}
              </Badge>
            ))}
        </Group>
      )}

      <Tabs value={activeView} onChange={(value) => setActiveView((value ?? "stage") as ViewName)}>
        <Tabs.List>
          {(Object.keys(VIEW_LABELS) as ViewName[]).map((view) => (
            <Tabs.Tab key={view} value={view}>{VIEW_LABELS[view]}</Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>

      {activeView === "stage" && <StageView dimension={dimension} />}
      {activeView === "transcript" && (
        <TranscriptView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
      {activeView === "timeline" && (
        <TimelineView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
    </Stack>
  );
}
```

- [ ] **Step 4: Run the tests to verify they all pass**

Run: `cd examples/web/frontend && npm run test -- src/routes/LiveTrialPage.test.tsx`
Expected: `7 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `82 passed` (unchanged — this file still has exactly 7 tests, rewritten not added to); build succeeds

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/LiveTrialPage.tsx examples/web/frontend/src/routes/LiveTrialPage.test.tsx
git commit -m "feat: rebuild LiveTrialPage on Mantine Tabs and SegmentedControl"
```

---

### Task 8: Rebuild `SetupPage` as a 4-step Mantine `Stepper` wizard

**Files:**
- Modify: `examples/web/frontend/src/routes/SetupPage.tsx`
- Modify: `examples/web/frontend/src/routes/SetupPage.test.tsx`

**Interfaces:**
- Consumes: `AgentConfigPanel` (Task 3), `getCatalog`/`startTrial`/`TrialConflictError`/`TrialConfigError` (unchanged), `render`/`screen`/`fireEvent`/`waitFor`/`within` from `../test/render` (Task 2).
- Produces: unchanged default export (`SetupPage(): JSX.Element`, no props).

**This task changes real behavior, not just markup** — the form becomes a genuine multi-step wizard (Text → Dimensions & settings → Agents → Review & start), each `Stepper.Step`'s content only rendering while that step is active. This is the one place in this plan where the test file isn't just adapted to new markup; it's substantially rewritten to drive the new step-by-step flow, and a few tests are genuinely new (the wizard navigation itself, the collapsed-agent-badge summary).

- [ ] **Step 1: Write the new test file against the wizard flow**

Replace `examples/web/frontend/src/routes/SetupPage.test.tsx` entirely:

```tsx
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { CatalogResponse } from "../api/types";
import SetupPage from "./SetupPage";
import { fireEvent, render, screen, waitFor, within } from "../test/render";

const fakeCatalog = {
  dimensions: [
    { name: "Character", dimension_type: "infringement" as const, importance: "high", description: "d", sub_dimensions: [] },
    { name: "Scenes a Faire", dimension_type: "exception" as const, importance: "medium", description: "d", sub_dimensions: [] },
  ],
  presets: [{ id: "infringing", label: "Infringing example", source_text: "SRC", target_text: "TGT" }],
  evaluation_strategies: [{ value: "fully_separate", label: "Fully separate", description: "d" }],
  provider_presets: [{ id: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1" }],
  env_status: { PSALM_API_KEY: true },
} as const satisfies CatalogResponse;

afterEach(() => {
  vi.restoreAllMocks();
});

function renderSetupPage() {
  return render(
    <MemoryRouter>
      <SetupPage />
    </MemoryRouter>,
  );
}

describe("SetupPage", () => {
  it("loads the catalog and shows the Text step first", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    expect(await screen.findByLabelText("Preset")).toBeInTheDocument();
    expect(screen.queryByLabelText("Character")).not.toBeInTheDocument();
  });

  it("applying a preset fills the source and target text fields", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    expect(screen.getByLabelText("Source text")).toHaveValue("SRC");
    expect(screen.getByLabelText("Target text")).toHaveValue("TGT");
  });

  it("advancing to the Dimensions step shows selectable dimensions", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    expect(await screen.findByLabelText("Character")).toBeInTheDocument();
    expect(screen.getByLabelText("Scenes a Faire")).toBeInTheDocument();
  });

  it("advancing to the Agents step shows each agent's env-var status as a badge", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    const prosecutorControl = (await screen.findByText("Prosecutor")).closest("button")!;
    expect(within(prosecutorControl).getByText("✓ using environment variable")).toBeInTheDocument();
  });

  it("expanding an agent panel reveals its configuration fields", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    await screen.findByText("Prosecutor");
    fireEvent.click(screen.getByText("Prosecutor"));
    const prosecutorGroup = await screen.findByRole("group", { name: "Prosecutor" });
    expect(within(prosecutorGroup).getByLabelText("API key")).toBeInTheDocument();
  });

  it("adds and removes jurors, never going below 3", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    await screen.findByText("Juror 0");
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(3);

    fireEvent.click(screen.getByText("Add juror"));
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(4);

    fireEvent.click(screen.getByText("Juror 3"));
    fireEvent.click(await screen.findByText("Remove juror 3"));
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(3);
  });

  it("disables Start Trial until source, target, and at least one dimension are set", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    expect(await screen.findByText("Start Trial")).toBeDisabled();
  });

  it("submits the trial with the right payload and navigates on success", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    const startTrialSpy = vi.spyOn(client, "startTrial").mockResolvedValue({ trial_id: "abc" });
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Start Trial"));

    await waitFor(() => expect(startTrialSpy).toHaveBeenCalled());
    const payload = startTrialSpy.mock.calls[0][0];
    expect(payload.source_text).toBe("SRC");
    expect(payload.dimensions).toContain("Character");
  });

  it("shows an error message when the backend reports a config error", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    vi.spyOn(client, "startTrial").mockRejectedValue(
      new client.TrialConfigError("PSALM-WEB-001", "No API key provided.", {}),
    );
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Start Trial"));

    expect(await screen.findByRole("alert")).toHaveTextContent("No API key provided.");
  });

  it("falls back to the generic env var when a role-specific env var is unset", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      ...fakeCatalog,
      env_status: { PSALM_API_KEY: true, PSALM_PROSECUTOR_API_KEY: false },
    });
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    const prosecutorControl = (await screen.findByText("Prosecutor")).closest("button")!;
    expect(within(prosecutorControl).getByText("✓ using environment variable")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/routes/SetupPage.test.tsx`
Expected: FAIL — most of these assertions describe wizard behavior (a "Next" button, dimensions hidden until step 2, agent panels collapsed with a badge) that doesn't exist yet on the current single-page component

- [ ] **Step 3: Rebuild the component as a 4-step wizard**

Replace `examples/web/frontend/src/routes/SetupPage.tsx` entirely:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Accordion, Badge, Button, Checkbox, Group, NativeSelect, NumberInput,
  Stack, Stepper, Text, Textarea, Title,
} from "@mantine/core";
import { TrialConfigError, TrialConflictError, getCatalog, startTrial } from "../api/client";
import type { AgentConfigInput, CatalogResponse, JurorConfigInput } from "../api/types";
import AgentConfigPanel from "../components/AgentConfigPanel";

function emptyAgentConfig(): AgentConfigInput {
  return {};
}

function emptyJurorConfig(): JurorConfigInput {
  return {};
}

function agentSummary(config: AgentConfigInput, envAvailable: boolean): string {
  const hasOverride = Boolean(
    config.base_url || config.api_key || config.model || config.temperature !== undefined,
  );
  if (hasOverride) return "configured";
  return envAvailable ? "✓ using environment variable" : "required";
}

export default function SetupPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  const [sourceText, setSourceText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [evaluationStrategy, setEvaluationStrategy] = useState("fully_separate");
  const [argumentationRounds, setArgumentationRounds] = useState(3);
  const [deliberationRounds, setDeliberationRounds] = useState(2);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(120);

  const [prosecutor, setProsecutor] = useState<AgentConfigInput>(emptyAgentConfig());
  const [defense, setDefense] = useState<AgentConfigInput>(emptyAgentConfig());
  const [judge, setJudge] = useState<AgentConfigInput>(emptyAgentConfig());
  const [jury, setJury] = useState<JurorConfigInput[]>([
    emptyJurorConfig(), emptyJurorConfig(), emptyJurorConfig(),
  ]);

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getCatalog().then(setCatalog).catch((e) => setCatalogError(String(e)));
  }, []);

  function applyPreset(presetId: string) {
    const preset = catalog?.presets.find((p) => p.id === presetId);
    if (!preset) return;
    setSourceText(preset.source_text);
    setTargetText(preset.target_text);
  }

  function toggleDimension(name: string) {
    setSelectedDimensions((current) => (
      current.includes(name) ? current.filter((d) => d !== name) : [...current, name]
    ));
  }

  function addJuror() {
    setJury((current) => [...current, emptyJurorConfig()]);
  }

  function removeJuror(index: number) {
    setJury((current) => (current.length <= 3 ? current : current.filter((_, i) => i !== index)));
  }

  async function handleSubmit() {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const { trial_id } = await startTrial({
        source_text: sourceText,
        target_text: targetText,
        dimensions: selectedDimensions,
        evaluation_strategy: evaluationStrategy,
        argumentation_rounds: argumentationRounds,
        deliberation_rounds: deliberationRounds,
        time_limit_seconds: timeLimitSeconds,
        prosecutor,
        defense,
        judge,
        jury,
      });
      navigate(`/trial/${trial_id}`);
    } catch (error) {
      if (error instanceof TrialConflictError) {
        setSubmitError("A trial is already in progress. Watch it, or wait for it to finish.");
      } else if (error instanceof TrialConfigError) {
        setSubmitError(`${error.code}: ${error.message}`);
      } else {
        setSubmitError(String(error));
      }
      setSubmitting(false);
    }
  }

  if (catalogError) {
    return <Text role="alert" c="red">Failed to load configuration options: {catalogError}</Text>;
  }
  if (!catalog) {
    return <Text>Loading...</Text>;
  }

  const canSubmit = (
    sourceText.trim() !== "" && targetText.trim() !== "" && selectedDimensions.length > 0 && !submitting
  );

  const agentPanels = [
    { label: "Prosecutor", config: prosecutor, onChange: setProsecutor, envKey: "PSALM_PROSECUTOR_API_KEY" },
    { label: "Defense", config: defense, onChange: setDefense, envKey: "PSALM_DEFENSE_API_KEY" },
    { label: "Judge", config: judge, onChange: setJudge, envKey: "PSALM_JUDGE_API_KEY" },
  ] as const;

  return (
    <Stack gap="lg" className="setup-page">
      <Title order={2}>New trial</Title>

      <Stepper active={step} onStepClick={setStep} allowNextStepsSelect={false}>
        <Stepper.Step label="Text">
          <Stack gap="sm" mt="md">
            <NativeSelect
              id="preset-select" label="Preset"
              placeholder="Choose a preset (optional)"
              data={catalog.presets.map((p) => ({ value: p.id, label: p.label }))}
              onChange={(e) => applyPreset(e.target.value)}
            />
            <Textarea
              id="source-text" label="Source text" value={sourceText}
              onChange={(e) => setSourceText(e.target.value)} minRows={6} autosize
            />
            <Textarea
              id="target-text" label="Target text" value={targetText}
              onChange={(e) => setTargetText(e.target.value)} minRows={6} autosize
            />
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Dimensions">
          <Stack gap="lg" mt="md">
            {(["infringement", "exception"] as const).map((type) => (
              <div key={type}>
                <Text fw={600} mb="xs">
                  {type === "infringement" ? "Infringement dimensions" : "Exception dimensions"}
                </Text>
                <Stack gap="xs">
                  {catalog.dimensions.filter((d) => d.dimension_type === type).map((d) => (
                    <Checkbox
                      key={d.name} label={d.name} title={d.description}
                      checked={selectedDimensions.includes(d.name)}
                      onChange={() => toggleDimension(d.name)}
                    />
                  ))}
                </Stack>
              </div>
            ))}

            <Accordion>
              <Accordion.Item value="advanced">
                <Accordion.Control>Advanced settings</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <NativeSelect
                      id="strategy-select" label="Evaluation strategy" value={evaluationStrategy}
                      data={catalog.evaluation_strategies.map((s) => ({ value: s.value, label: s.label }))}
                      onChange={(e) => setEvaluationStrategy(e.target.value)}
                    />
                    <NumberInput
                      id="argumentation-rounds" label="Argumentation rounds" min={1}
                      value={argumentationRounds}
                      onChange={(value) => setArgumentationRounds(Number(value))}
                    />
                    <NumberInput
                      id="deliberation-rounds" label="Deliberation rounds" min={1}
                      value={deliberationRounds}
                      onChange={(value) => setDeliberationRounds(Number(value))}
                    />
                    <NumberInput
                      id="time-limit" label="Time limit (seconds)" min={1}
                      value={timeLimitSeconds}
                      onChange={(value) => setTimeLimitSeconds(Number(value))}
                    />
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Agents">
          <Stack gap="md" mt="md">
            <Accordion multiple defaultValue={[]}>
              {agentPanels.map((agent) => (
                <Accordion.Item key={agent.label} value={agent.label}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md">
                      <Text>{agent.label}</Text>
                      <Badge variant="light" color="gray">
                        {agentSummary(
                          agent.config,
                          catalog.env_status[agent.envKey] || catalog.env_status.PSALM_API_KEY,
                        )}
                      </Badge>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <AgentConfigPanel
                      label={agent.label} config={agent.config} onChange={agent.onChange}
                      envAvailable={catalog.env_status[agent.envKey] || catalog.env_status.PSALM_API_KEY}
                      providerPresets={catalog.provider_presets}
                    />
                  </Accordion.Panel>
                </Accordion.Item>
              ))}

              {jury.map((jurorConfig, index) => (
                <Accordion.Item key={index} value={`Juror ${index}`}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md">
                      <Text>Juror {index}</Text>
                      <Badge variant="light" color="gray">
                        {agentSummary(
                          jurorConfig,
                          catalog.env_status.PSALM_JURY_API_KEY || catalog.env_status.PSALM_API_KEY,
                        )}
                      </Badge>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <Stack gap="sm">
                      <AgentConfigPanel
                        label={`Juror ${index}`} config={jurorConfig}
                        onChange={(updated) => setJury((current) => (
                          current.map((j, i) => (i === index ? { ...updated, seed: j.seed } : j))
                        ))}
                        envAvailable={catalog.env_status.PSALM_JURY_API_KEY || catalog.env_status.PSALM_API_KEY}
                        providerPresets={catalog.provider_presets}
                      />
                      {jury.length > 3 && (
                        <Button variant="subtle" color="red" onClick={() => removeJuror(index)}>
                          Remove juror {index}
                        </Button>
                      )}
                    </Stack>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
            <Button variant="light" onClick={addJuror}>Add juror</Button>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Review">
          <Stack gap="md" mt="md">
            <div>
              <Text fw={600}>Source text</Text>
              <Text size="sm" c="dimmed">{sourceText || "(empty)"}</Text>
            </div>
            <div>
              <Text fw={600}>Target text</Text>
              <Text size="sm" c="dimmed">{targetText || "(empty)"}</Text>
            </div>
            <div>
              <Text fw={600}>Dimensions</Text>
              <Text size="sm" c="dimmed">
                {selectedDimensions.length > 0 ? selectedDimensions.join(", ") : "(none selected)"}
              </Text>
            </div>
            {submitError && <Text role="alert" c="red">{submitError}</Text>}
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {submitting ? "Starting..." : "Start Trial"}
            </Button>
          </Stack>
        </Stepper.Step>
      </Stepper>

      <Group justify="space-between">
        <Button variant="default" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
          Back
        </Button>
        {step < 3 && (
          <Button onClick={() => setStep((s) => Math.min(3, s + 1))}>Next</Button>
        )}
      </Group>
    </Stack>
  );
}
```

Mantine's `Stepper` only renders the active step's children — this is why dimensions/agents/review content is invisible until you navigate there, matching the new test file's expectations. `Accordion.Control` renders as a real `<button>`, so `.closest("button")` from any text inside it reaches the clickable control, and clicking it (or any of its children, via event bubbling) toggles that `Accordion.Item` open — matching how the tests click the agent/juror labels directly.

- [ ] **Step 4: Run the tests to verify they all pass**

Run: `cd examples/web/frontend && npm run test -- src/routes/SetupPage.test.tsx`
Expected: `10 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `85 passed` (82 from Task 7 + 3 net-new in this file: 10 now vs. 7 before); build succeeds

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/SetupPage.tsx examples/web/frontend/src/routes/SetupPage.test.tsx
git commit -m "feat: rebuild SetupPage as a 4-step Mantine wizard"
```

---

### Task 9: Rebuild `ResultsPage` on Mantine (`Alert`, `Table`, `Accordion`, `ActionIcon` + `Slider`)

**Files:**
- Modify: `examples/web/frontend/src/routes/ResultsPage.tsx`
- Modify: `examples/web/frontend/src/routes/ResultsPage.test.tsx`

**Interfaces:**
- Consumes: `fetchTrialEvents`/`getTrial` (unchanged), `useTrialStore` (unchanged), `StageView` (Task 4), `render`/`screen`/`act` from `../test/render` (Task 2).
- Produces: unchanged default export (`ResultsPage(): JSX.Element`, no props).

**No behavior change in this task** — every existing test's assertions target text content or the `startReplay`/`fetchTrialEvents`/`liveTrialId` fast-path/fetch-path logic, none of which changes here (only the surrounding markup does). All 6 existing tests are expected to keep passing with just the import-source swap.

- [ ] **Step 1: Update the test file to use the shared render helper**

Replace `examples/web/frontend/src/routes/ResultsPage.test.tsx` entirely:

```tsx
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { PSALMEvent, TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import ResultsPage from "./ResultsPage";
import { act, render, screen } from "../test/render";

const fakeDetail: TrialDetail = {
  id: "abc", created_at: "t", status: "done", source_text_preview: "s", target_text_preview: "t",
  verdict: "Guilty", error_message: null,
  config_summary: {},
  result: {
    verdict: "Guilty", rationale: "Strong evidence throughout.",
    dimension_verdicts: [
      {
        dimension: "Character", dimension_type: "infringement", importance: "high", verdict: "Guilty",
        weighted_score: 0.8,
        argumentation_log: { rounds: [], prosecution_closing_argument: null, defense_closing_argument: null },
        debate_log: { rounds: [], final_voting_strategy_applied: "unanimous" },
      },
    ],
    metadata: {
      duration_seconds: 5, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
      voting_strategy_applied: "unanimous", agent_failures: [],
    },
  },
};

function renderAtResult(trialId: string) {
  return render(
    <MemoryRouter initialEntries={[`/trial/${trialId}/result`]}>
      <Routes>
        <Route path="/trial/:trialId/result" element={<ResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ResultsPage", () => {
  beforeEach(() => {
    useTrialStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the verdict and rationale once loaded", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    renderAtResult("abc");
    expect(await screen.findByText("Verdict: Guilty")).toBeInTheDocument();
    expect(screen.getByText("Strong evidence throughout.")).toBeInTheDocument();
  });

  it("shows the per-dimension breakdown table", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");
    expect(screen.getByText("0.80")).toBeInTheDocument();
  });

  it("shows an error banner for a failed trial", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue({
      ...fakeDetail, status: "error", error_message: "LLM connection failed.", result: null,
    });
    renderAtResult("abc");
    expect(await screen.findByText(/Trial failed: LLM connection failed\./)).toBeInTheDocument();
  });

  it("shows a Replay button only when live events were buffered, and starts replay mode on click", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    const fetchSpy = vi.spyOn(client, "fetchTrialEvents");
    useTrialStore.setState({ allEvents: [{ type: "run_started" } as PSALMEvent], liveTrialId: "abc" });
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");

    const replayButton = screen.getByText("Replay this trial");
    act(() => {
      replayButton.click();
    });
    expect(screen.getByText("Replay")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows a working Replay button that fetches the trial's events when none are buffered (e.g. loaded from history)", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    const fetchedEvents = [{ type: "run_started" } as PSALMEvent];
    const fetchSpy = vi.spyOn(client, "fetchTrialEvents").mockResolvedValue(fetchedEvents);
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");

    const replayButton = screen.getByText("Replay this trial");
    await act(async () => {
      replayButton.click();
    });

    expect(fetchSpy).toHaveBeenCalledWith("abc");
    expect(useTrialStore.getState().allEvents).toEqual(fetchedEvents);
    expect(screen.getByText("Replay")).toBeInTheDocument();
  });

  it("shows Replay for a finished trial even when buffered live events belong to a different trial, and fetches the correct trial's events on click", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    const staleEvents = [{ type: "run_started" } as PSALMEvent];
    const fetchedEvents = [{ type: "final_verdict_reached" } as PSALMEvent];
    const fetchSpy = vi.spyOn(client, "fetchTrialEvents").mockResolvedValue(fetchedEvents);
    useTrialStore.setState({ allEvents: staleEvents, liveTrialId: "some-other-trial" });
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");

    const replayButton = screen.getByText("Replay this trial");
    expect(replayButton).toBeInTheDocument();
    await act(async () => {
      replayButton.click();
    });

    expect(fetchSpy).toHaveBeenCalledWith("abc");
    expect(useTrialStore.getState().allEvents).toEqual(fetchedEvents);
    expect(useTrialStore.getState().allEvents).not.toEqual(staleEvents);
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/routes/ResultsPage.test.tsx`
Expected: `6 passed` — this only proves the test file itself (with its swapped import) is still valid; no behavior is changing yet

- [ ] **Step 3: Rebuild the component on Mantine**

Replace `examples/web/frontend/src/routes/ResultsPage.tsx` entirely:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  ActionIcon, Alert, Accordion, Badge, Button, Group, Slider, Stack, Table, Text, Title,
} from "@mantine/core";
import { IconPlayerPause, IconPlayerPlay } from "@tabler/icons-react";
import { fetchTrialEvents, getTrial } from "../api/client";
import type { TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import StageView from "../views/StageView";

export default function ResultsPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const [detail, setDetail] = useState<TrialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReplay, setShowReplay] = useState(false);
  const [replayDimension, setReplayDimension] = useState<string | null>(null);
  const [isLoadingReplay, setIsLoadingReplay] = useState(false);

  const liveEvents = useTrialStore((s) => s.allEvents);
  const liveTrialId = useTrialStore((s) => s.liveTrialId);
  const loadForReplay = useTrialStore((s) => s.loadForReplay);
  const replayState = useTrialStore((s) => s.state);
  const replayMode = useTrialStore((s) => s.mode);
  const isPlaying = useTrialStore((s) => s.isPlaying);
  const replayIndex = useTrialStore((s) => s.replayIndex);
  const play = useTrialStore((s) => s.play);
  const pause = useTrialStore((s) => s.pause);
  const scrubTo = useTrialStore((s) => s.scrubTo);

  useEffect(() => {
    if (!trialId) return;
    getTrial(trialId).then(setDetail).catch((e) => setError(String(e)));
  }, [trialId]);

  useEffect(() => {
    if (!replayDimension && replayState.dimensionOrder.length > 0) {
      setReplayDimension(replayState.dimensionOrder[0]);
    }
  }, [replayState.dimensionOrder, replayDimension]);

  function startReplay() {
    if (liveTrialId === trialId && liveEvents.length > 0) {
      loadForReplay(liveEvents);
      setShowReplay(true);
      return;
    }
    if (!trialId) return;
    setIsLoadingReplay(true);
    fetchTrialEvents(trialId).then((events) => {
      loadForReplay(events);
      setShowReplay(true);
      setIsLoadingReplay(false);
    });
  }

  if (error) return <Alert role="alert" color="red">Failed to load trial: {error}</Alert>;
  if (!detail) return <Text>Loading...</Text>;

  const result = detail.result;

  function verdictColor(verdict: string): string {
    if (verdict === "Guilty") return "red";
    if (verdict === "Not Guilty") return "green";
    return "gray";
  }

  return (
    <Stack gap="lg" className="results-page">
      <Title order={2}>Trial result</Title>
      {detail.status === "error" && (
        <Alert role="alert" color="red">Trial failed: {detail.error_message}</Alert>
      )}

      {result && (
        <>
          <Alert color={verdictColor(result.verdict)} title={`Verdict: ${result.verdict}`} className="verdict-banner">
            {result.rationale}
          </Alert>

          <Stack gap="sm">
            <Title order={4}>Per-dimension breakdown</Title>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Dimension</Table.Th><Table.Th>Type</Table.Th><Table.Th>Importance</Table.Th>
                  <Table.Th>Verdict</Table.Th><Table.Th>Score</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {result.dimension_verdicts.map((dv) => (
                  <Table.Tr key={dv.dimension}>
                    <Table.Td>{dv.dimension}</Table.Td>
                    <Table.Td>{dv.dimension_type}</Table.Td>
                    <Table.Td>{dv.importance}</Table.Td>
                    <Table.Td>
                      <Badge color={verdictColor(dv.verdict)} variant="light">{dv.verdict}</Badge>
                    </Table.Td>
                    <Table.Td>{dv.weighted_score.toFixed(2)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Stack>

          <Accordion>
            {result.dimension_verdicts.map((dv) => (
              <Accordion.Item key={dv.dimension} value={dv.dimension}>
                <Accordion.Control>{dv.dimension} — full log</Accordion.Control>
                <Accordion.Panel>
                  <Title order={5}>Argumentation</Title>
                  {dv.argumentation_log.rounds.map((round) => (
                    <div key={round.round}>
                      <Text fw={600} size="sm" mt="sm">Round {round.round}</Text>
                      {round.prosecution_arguments.map((arg, i) => <Text key={`pa${i}`} size="sm">Prosecution: {arg.claim}</Text>)}
                      {round.prosecution_rejected_arguments.map((rej, i) => (
                        <Text key={`pr${i}`} size="sm" c="dimmed">Rejected (prosecution): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                      {round.defense_counters.map((arg, i) => <Text key={`dc${i}`} size="sm">Defense counters: {arg.claim}</Text>)}
                      {round.defense_counter_rejected_arguments.map((rej, i) => (
                        <Text key={`dcr${i}`} size="sm" c="dimmed">Rejected (defense counter): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                      {round.defense_arguments.map((arg, i) => <Text key={`da${i}`} size="sm">Defense: {arg.claim}</Text>)}
                      {round.defense_rejected_arguments.map((rej, i) => (
                        <Text key={`dr${i}`} size="sm" c="dimmed">Rejected (defense): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                      {round.prosecution_counters.map((arg, i) => (
                        <Text key={`pc${i}`} size="sm">Prosecution counters: {arg.claim}</Text>
                      ))}
                      {round.prosecution_counter_rejected_arguments.map((rej, i) => (
                        <Text key={`pcr${i}`} size="sm" c="dimmed">Rejected (prosecution counter): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                    </div>
                  ))}
                  {dv.argumentation_log.prosecution_closing_argument && (
                    <Text size="sm" mt="sm">Prosecution closing: {dv.argumentation_log.prosecution_closing_argument}</Text>
                  )}
                  {dv.argumentation_log.defense_closing_argument && (
                    <Text size="sm">Defense closing: {dv.argumentation_log.defense_closing_argument}</Text>
                  )}

                  <Title order={5} mt="md">Deliberation</Title>
                  {dv.debate_log.rounds.map((round) => (
                    <div key={round.round}>
                      <Text fw={600} size="sm" mt="sm">Round {round.round}</Text>
                      {round.votes.map((vote) => (
                        <Text key={vote.juror_id} size="sm">{vote.juror_id}: {vote.vote} — {vote.rationale}</Text>
                      ))}
                      {round.discussion_messages.map((msg, i) => (
                        <Text key={i} size="sm">{msg.juror_id}: {msg.message}</Text>
                      ))}
                    </div>
                  ))}
                </Accordion.Panel>
              </Accordion.Item>
            ))}
          </Accordion>
        </>
      )}

      {detail.status !== "running" && !showReplay && (
        <Button onClick={startReplay} disabled={isLoadingReplay} variant="light">
          {isLoadingReplay ? "Loading replay..." : "Replay this trial"}
        </Button>
      )}

      {showReplay && replayMode === "replay" && (
        <Stack gap="sm" className="replay-section">
          <Title order={4}>Replay</Title>
          {replayState.dimensionOrder.length > 1 && (
            <Group gap="xs" className="dimension-selector">
              {replayState.dimensionOrder.map((name) => (
                <Badge
                  key={name} variant={name === replayDimension ? "filled" : "light"}
                  color="gold" style={{ cursor: "pointer" }}
                  onClick={() => setReplayDimension(name)}
                >
                  {name}
                </Badge>
              ))}
            </Group>
          )}
          <Group gap="sm" align="center" className="replay-controls">
            <ActionIcon
              onClick={isPlaying ? pause : play} variant="filled" size="lg"
              aria-label={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <IconPlayerPause size={18} /> : <IconPlayerPlay size={18} />}
            </ActionIcon>
            <Slider
              style={{ flex: 1 }}
              min={-1} max={Math.max(liveEvents.length - 1, 0)} value={replayIndex}
              onChange={scrubTo} label={null}
            />
          </Group>
          <StageView dimension={replayDimension ? replayState.dimensions[replayDimension] ?? null : null} />
        </Stack>
      )}
    </Stack>
  );
}
```

- [ ] **Step 4: Run the tests to verify they still pass**

Run: `cd examples/web/frontend && npm run test -- src/routes/ResultsPage.test.tsx`
Expected: `6 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `85 passed` (unchanged from Task 8 — this file still has exactly 6 tests); build succeeds

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/ResultsPage.tsx examples/web/frontend/src/routes/ResultsPage.test.tsx
git commit -m "feat: rebuild ResultsPage on Mantine"
```

---

### Task 10: Rebuild `HistoryPage` on Mantine `Table`

**Files:**
- Modify: `examples/web/frontend/src/routes/HistoryPage.tsx`
- Modify: `examples/web/frontend/src/routes/HistoryPage.test.tsx`

**Interfaces:**
- Consumes: `listTrials`/`TrialSummary` (unchanged), `render`/`screen` from `../test/render` (Task 2).
- Produces: unchanged default export (`HistoryPage(): JSX.Element`, no props).

**No behavior change in this task** — same three tests, same assertions, only the import source changes.

- [ ] **Step 1: Update the test file to use the shared render helper**

Replace `examples/web/frontend/src/routes/HistoryPage.test.tsx` entirely:

```tsx
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import HistoryPage from "./HistoryPage";
import { render, screen } from "../test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HistoryPage", () => {
  it("shows a message when there are no trials yet", async () => {
    vi.spyOn(client, "listTrials").mockResolvedValue([]);
    render(<MemoryRouter><HistoryPage /></MemoryRouter>);
    expect(await screen.findByText("No trials run yet this session.")).toBeInTheDocument();
  });

  it("lists each trial with its status and verdict", async () => {
    vi.spyOn(client, "listTrials").mockResolvedValue([
      {
        id: "abc", created_at: "2026-01-01T00:00:00Z", status: "done",
        source_text_preview: "s", target_text_preview: "t", verdict: "Guilty", error_message: null,
      },
    ]);
    render(<MemoryRouter><HistoryPage /></MemoryRouter>);
    expect(await screen.findByText(/done/)).toBeInTheDocument();
    expect(screen.getByText(/Guilty/)).toBeInTheDocument();
  });

  it("links a running trial to the live view and a finished one to the results page", async () => {
    vi.spyOn(client, "listTrials").mockResolvedValue([
      {
        id: "running-1", created_at: "t", status: "running",
        source_text_preview: "s", target_text_preview: "t", verdict: null, error_message: null,
      },
      {
        id: "done-1", created_at: "t", status: "done",
        source_text_preview: "s", target_text_preview: "t", verdict: "Guilty", error_message: null,
      },
    ]);
    render(<MemoryRouter><HistoryPage /></MemoryRouter>);
    await screen.findByText(/running/);
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/trial/running-1");
    expect(links[1]).toHaveAttribute("href", "/trial/done-1/result");
  });
});
```

- [ ] **Step 2: Run the tests against the current component**

Run: `cd examples/web/frontend && npm run test -- src/routes/HistoryPage.test.tsx`
Expected: `3 passed` — confirms the test file (with its swapped import) is valid before the rebuild

- [ ] **Step 3: Rebuild the component on Mantine's `Table`**

Replace `examples/web/frontend/src/routes/HistoryPage.tsx` entirely:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Anchor, Badge, Stack, Table, Text, Title } from "@mantine/core";
import { listTrials } from "../api/client";
import type { TrialSummary } from "../api/types";

function statusColor(status: string): string {
  if (status === "done") return "green";
  if (status === "error") return "red";
  return "gold";
}

export default function HistoryPage() {
  const [trials, setTrials] = useState<TrialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTrials().then(setTrials).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Text role="alert" c="red">Failed to load trial history: {error}</Text>;
  if (!trials) return <Text>Loading...</Text>;

  return (
    <Stack gap="md" className="history-page">
      <Title order={2}>Trial history</Title>
      {trials.length === 0 && <Text>No trials run yet this session.</Text>}
      {trials.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Created</Table.Th><Table.Th>Status</Table.Th><Table.Th>Verdict</Table.Th><Table.Th>Texts</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {trials.map((trial) => (
              <Table.Tr key={trial.id}>
                <Table.Td>
                  <Anchor
                    component={Link}
                    to={trial.status === "running" ? `/trial/${trial.id}` : `/trial/${trial.id}/result`}
                  >
                    {trial.created_at}
                  </Anchor>
                </Table.Td>
                <Table.Td><Badge color={statusColor(trial.status)} variant="light">{trial.status}</Badge></Table.Td>
                <Table.Td>{trial.verdict ?? "—"}</Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{trial.source_text_preview} → {trial.target_text_preview}</Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
```

- [ ] **Step 4: Run the tests to verify they still pass**

Run: `cd examples/web/frontend && npm run test -- src/routes/HistoryPage.test.tsx`
Expected: `3 passed`

- [ ] **Step 5: Run the full suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `85 passed` (unchanged — this file still has exactly 3 tests); build succeeds

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/HistoryPage.tsx examples/web/frontend/src/routes/HistoryPage.test.tsx
git commit -m "feat: rebuild HistoryPage on Mantine Table"
```

---

### Task 11: Trim `index.css` and run final full-repo verification

**Files:**
- Modify: `examples/web/frontend/src/index.css`

**Interfaces:**
- Consumes: everything from Tasks 1–10.
- Produces: nothing further — this is the last task in the plan.

- [ ] **Step 1: Trim the now-redundant global reset rules**

`@mantine/core/styles.css` (imported in `main.tsx` since Task 2) already provides its own CSS reset (box-sizing, margin resets) and drives the page background/text color from the active theme via CSS variables once `MantineProvider` is mounted — the original manual `* { box-sizing: border-box; }` and `body { margin: 0; font-family: ...; background: #0f1115; color: #e6e6e6; }` rules are now both redundant and stale (that background/color pair predates the approved Hybrid palette). Replace `examples/web/frontend/src/index.css` entirely, keeping only the pulse keyframe added in Task 4:

```css
@keyframes stage-speech-pulse {
  from { background-color: rgba(201, 168, 58, 0.35); }
  to { background-color: transparent; }
}

.stage-speech-pulse {
  animation: stage-speech-pulse 900ms ease-out;
  border-radius: 4px;
  padding: 2px 6px;
}
```

- [ ] **Step 2: Run the full frontend suite and build**

Run: `cd examples/web/frontend && npm run test && npm run build`
Expected: `85 passed`; build succeeds with no TypeScript errors

- [ ] **Step 3: Confirm no regressions in the backend or SDK**

This plan never touches `examples/web/backend/` or `psalm/`, but confirm nothing else on the branch broke:

```bash
uv run pytest tests/ -q
uv run pytest examples/web/backend/tests/ -v
uv run ruff check psalm/ tests/ examples/web/backend/
```

Expected: the main `psalm` SDK suite passes exactly as before this plan, the web backend suite passes in full, ruff is clean

- [ ] **Step 4: Check for dependency vulnerabilities in the new packages**

```bash
cd examples/web/frontend && npm audit --omit=dev
```

Expected: `0 vulnerabilities` in production dependencies (any findings in `devDependencies` — e.g. from the Vite/Vitest toolchain — are not a blocker for this plan, consistent with this project's existing precedent)

- [ ] **Step 5: Manual visual pass (requires a browser — do this, or flag it clearly if you can't)**

```bash
cd examples/web/frontend && npm run dev
```

Open the printed dev server URL and click through every page: Setup (all 4 wizard steps, including expanding an agent panel and adding/removing a juror), History (empty state), and — if a `psalm`-compatible API key is available in this environment — a live trial through to its Results page with Replay. Confirm: dark theme renders consistently, no layout overflow/clipping, no console errors, and the Stage view's speech-bubble pulse is visible when new dialogue arrives. If this environment has no browser access or no API key, say so explicitly rather than claiming this step was verified — this mirrors how the original courtroom-web-demo plan's Task 20 Step 4 deferred its equivalent live-trial check to a human with real credentials.

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/index.css
git commit -m "chore: trim index.css now that Mantine owns global styling"
```

---
