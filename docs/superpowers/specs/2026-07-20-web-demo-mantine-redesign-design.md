# Courtroom Web Demo — Mantine Visual Redesign

## 1. Overview

The `examples/web/` courtroom demo (backend + React frontend, built in a prior
plan) is functionally complete but visually unstyled: the frontend ships a
single 10-line `index.css` that only resets `box-sizing` and sets a page
background/font. Every component uses semantic `className`s (`stage-podium`,
`transcript-entry`, `dimension-selector`, etc.) with no corresponding CSS
anywhere, so the app renders as raw, unstyled HTML — no layout, no visual
hierarchy, default browser form controls. This makes the app "practically
unusable" as a demo, per the request that opened this design.

Separately, a real bug was found and already fixed on `v2` (commit
`ea6414d`, prior to this design work): `closing_statement_delivered` and
`closing_argument_delivered` events — both of which represent a party
speaking — never updated `DimensionState.speakingRole`/`latestSpeech`, the
only fields the Stage view's speech bubble reads. Transcript/Timeline kept
advancing normally (they render the full transcript array) while Stage
visibly froze during closing statements/arguments. That fix is out of scope
for this design; it's mentioned here only because it was the other half of
the original complaint ("the courtroom stage doesn't update properly").

This design covers the remaining half: applying a real design system
(Mantine) across the entire existing frontend, plus a small set of
information-architecture improvements the redesign makes natural to include
(chiefly: turning the very long, flat Setup form into a guided wizard).

**Goal:** every existing page/flow keeps its current functionality and data
flow, but is rebuilt visually with Mantine components and a consistent dark
theme, with the Setup page reorganized into a 4-step wizard and the Stage
view gaining an explicit "just updated" visual cue.

## 2. Architecture

### 2.1 Dependencies

Add to `examples/web/frontend/package.json`:
- `@mantine/core`, `@mantine/hooks`, `@mantine/form` (runtime)
- `@tabler/icons-react` (icon set — scales, gavel, users, play/pause, etc.)
- `@testing-library/user-event` (devDependency — needed for correctly
  simulating interaction with Mantine's non-native components in tests; see
  §6)

### 2.2 Theme setup

Wrap the app root (`main.tsx`) in Mantine's `MantineProvider` with a custom
`theme` object exported from a new `src/theme.ts`. Dark color scheme only —
no light/dark toggle (decided explicitly: doubling the visual/QA surface
wasn't judged worth it for a focused demo).

**Palette ("Hybrid" — the visual direction approved during brainstorming):**
- Page background: `#14152a`
- Card/panel surface: `#1e1f38`
- Secondary surface: `#2a2b45`
- Primary/accent (buttons, "currently active/speaking" highlights): `#c9a83a`
- Accent glow/emphasis: `#d4a33a`
- Verdict semantics reuse Mantine's default green/red/gray scales for
  Guilty / Not Guilty / Undecided respectively, kept legible against the
  dark background
- Typography: system sans-serif throughout (no serif) — deliberately not a
  fully skeuomorphic "wood and parchment" courtroom look; icons from
  `@tabler/icons-react` are used sparingly as accents (scales, gavel, users)
  on headers/badges, not as decorative backgrounds

### 2.3 Component-selection principle

This governs both visual consistency and how much of the existing test
suite needs rewriting, so it's stated as an explicit rule for every task in
the implementation plan to follow:

- **Prefer Mantine components backed by a real native form element** —
  `TextInput`, `PasswordInput`, `NumberInput`, `Textarea`, `Checkbox`,
  `NativeSelect`, `Button` — wherever one exists for what's being built.
  These render actual `<input>`/`<select>`/`<button>` elements under
  Mantine's styling wrapper, so existing `getByLabelText`, `fireEvent.change`,
  and `getByRole("button")` queries keep working with only markup-detail
  adjustments (e.g. wrapper `div`s around the label).
- **Adopt Mantine's real (non-native) component** where no sensible native
  equivalent exists for the interaction being built — the view/dimension
  switcher (`Tabs`), the setup wizard (`Stepper`), per-dimension full logs
  (`Accordion`), replay scrubbing (`Slider`), the results/history tables
  (`Table`). These get proper ARIA semantics, keyboard navigation, and
  visual polish essentially for free. Updating that component's tests to
  Testing-Library's recommended interaction patterns (role-based queries,
  `userEvent`) is treated as in-scope work for the same task that builds
  the component — not a follow-up or an afterthought.

## 3. Page-by-Page Design

### 3.1 App shell

Mantine `AppShell` with a slim header. The existing two nav links ("New
trial", "History") become Mantine `NavLink`s. No new navigation items.

### 3.2 SetupPage → 4-step wizard

Currently one long flat page (text → dimensions → advanced settings → 3
fixed agent panels → N juror panels → submit). Rebuilt as a Mantine
`Stepper` with 4 non-linear-navigable steps (the user can jump back to any
completed step, not just move forward):

1. **Text** — preset `NativeSelect`, source/target `Textarea`s.
2. **Dimensions & settings** — dimension checkboxes grouped by
   infringement/exception type (`Checkbox.Card` grid, more scannable than a
   plain checkbox list); advanced settings (evaluation strategy,
   argumentation/deliberation rounds, time limit) inside a collapsed
   `Accordion` panel within this step, replacing today's "Show/Hide
   advanced settings" toggle button with the same collapsed-by-default
   behavior.
3. **Agents** — Prosecutor, Defense, Judge, and each juror as an
   `Accordion.Item`, collapsed by default showing a one-line summary
   (a `Badge` reading "✓ using environment variable" when no override is
   set, or "configured" once one is). Expanding reveals the same
   provider/base-URL/API-key/model/temperature fields as today. Add/remove
   juror behavior is unchanged (minimum of 3), just restyled.
4. **Review & start** — read-only summary of every choice made across steps
   1–3 (source/target text preview, selected dimensions, per-agent
   configuration summary), the "Start Trial" button, and the submit-error
   `Alert` (409 conflict / 400 config error / generic fallback — same three
   cases as today, unchanged behavior).

This form is filled out once per trial, not repeatedly, so an
extra-clicks-to-go-back cost is acceptable in exchange for a much less
overwhelming first-touch experience — a live walkthrough of "1 → 2 → 3 → 4 →
Start" also demos well.

### 3.3 LiveTrialPage

The Stage/Transcript/Timeline switcher becomes a Mantine `Tabs` (replacing
the current plain `<button>`s with a manually-toggled `active` class). The
dimension selector, shown only when 2+ dimensions are running, becomes a
`SegmentedControl`. The background-dimension status strip (added in a
previous scope-gap fix) becomes a row of small `Badge`s instead of plain
text.

### 3.4 StageView

The largest visual rebuild:
- Judge bench: a header `Card` with a scales icon.
- Prosecutor/Defense: two `Card` "podiums" side by side; whichever is
  currently speaking gets a gold glow border (`#d4a33a`).
- Jury tally: colored `Badge`s per vote count, plus a juror speech bubble
  (existing behavior) when a juror is discussing.
- **New — directly addressing the "hard to tell if anything updated"
  complaint**: the speech bubble briefly pulses/highlights on arrival, keyed
  to the underlying event's `id` (a short CSS transition, not a persistent
  animation). This makes a new line of dialogue visually unmistakable the
  instant it lands, rather than relying on the viewer to notice a text diff
  themselves — this is a genuine UX gap independent of the reducer bug that
  was already fixed, since even correctly-updating content is easy to miss
  with zero visual feedback.

### 3.5 TranscriptView

Rebuilt on Mantine's `Timeline` component (icon + connecting line per
entry — a natural fit for a transcript feed), retaining today's
role-based color coding. Also gains auto-scroll-to-newest-entry, closing out
a previously-identified gap (the view didn't auto-scroll despite the
original spec calling for it) while this file is already being rebuilt.

### 3.6 TimelineView

The phase stepper (Setup → Argumentation rounds → Deliberation → Verdict)
becomes a non-interactive Mantine `Stepper` showing done/current/upcoming
status per step, with the merged transcript rendered below it exactly as
today.

### 3.7 ResultsPage

- Verdict banner: a large `Alert`/`Card`, icon and color keyed to the
  verdict (Guilty / Not Guilty / Undecided).
- Per-dimension score table: Mantine `Table`.
- Full argumentation/deliberation log per dimension: Mantine `Accordion`,
  one item per dimension (replacing the existing `<details>`/`<summary>`).
- Replay controls: `ActionIcon` for play/pause, Mantine `Slider` for
  scrubbing (replacing the native `<input type="range">`).
- "Replay this trial" availability/fetch-path logic (any finished trial,
  not just the one just watched live — an earlier scope-gap fix) is
  unchanged; only its presentation changes.

### 3.8 HistoryPage

The trial list becomes a Mantine `Table` with status `Badge`s (running /
done / error) instead of plain text, linking to the live or results page
exactly as today.

## 4. Testing Strategy

Every existing frontend test file is touched, since markup changes
throughout the app. See §2.3 for the two-tier approach (native-backed
components need minimal query changes; non-native components need
role/ARIA-based query rewrites using `@testing-library/user-event`).

**Environment setup gotcha to resolve first:** Mantine's interactive
components rely on browser APIs jsdom doesn't implement by default
(`ResizeObserver`, `matchMedia`, `getBoundingClientRect`). `src/test/setup.ts`
needs mocks for these before any Mantine component test can run. This
becomes the implementation plan's first task — mirroring how the original
plan's Task 8 established Vite/Vitest scaffolding before any component work
began — so it's resolved once up front rather than rediscovered on every
later task.

No new test tooling beyond `@testing-library/user-event`; no visual
regression/snapshot tooling is introduced.

## 5. Error Handling

No behavior changes. The same three error paths continue to work exactly as
today — a 409 trial-conflict response, a 400 config-error response, and a
generic fallback, plus the `RunFailed` event's error banner on
`ResultsPage`. Only presentation changes: plain `<p role="alert">` elements
become Mantine `Alert` components (which support `role="alert"`, so
existing error-message test queries are unaffected).

No toast/notification system is introduced — that would be a UX expansion
beyond "make what exists look good," and inline banners already match how
the app communicates errors today.

## 6. Breaking Changes

None to the backend or the `psalm` SDK — this is a 100%-frontend visual and
layout change. The frontend's state/data-flow architecture (the shared
`applyEvent` reducer, the Zustand store, the SSE event pipeline) is
unchanged; only rendering changes. Every frontend component test file is
expected to require modification as part of this work — that's expected
scope, not an unplanned side effect.

## 7. Files Added / Modified

**Added:**
- `examples/web/frontend/src/theme.ts` (Mantine theme definition)

**Modified (styling/markup rebuild, plus test-file updates for each):**
- `examples/web/frontend/src/main.tsx` (MantineProvider wiring)
- `examples/web/frontend/src/App.tsx` (AppShell + nav)
- `examples/web/frontend/src/routes/SetupPage.tsx` (wizard rebuild)
- `examples/web/frontend/src/routes/LiveTrialPage.tsx`
- `examples/web/frontend/src/routes/ResultsPage.tsx`
- `examples/web/frontend/src/routes/HistoryPage.tsx`
- `examples/web/frontend/src/views/StageView.tsx`
- `examples/web/frontend/src/views/TranscriptView.tsx`
- `examples/web/frontend/src/views/TimelineView.tsx`
- `examples/web/frontend/src/components/AgentConfigPanel.tsx`
- `examples/web/frontend/src/test/setup.ts` (jsdom/Mantine environment mocks)
- `examples/web/frontend/package.json` / `package-lock.json`
- `examples/web/frontend/src/index.css` (likely reduced to near-nothing,
  since Mantine owns styling — kept only if a handful of truly global rules
  remain necessary)

**Unchanged:** everything under `examples/web/backend/`, the `psalm` SDK
itself, `src/state/eventReducer.ts` and `src/state/store.ts` (data flow
logic — only their consumers' rendering changes), `src/api/` (client and
types).

## 8. Unchanged / Explicitly Out of Scope

- No light/dark mode toggle — dark-only, per the palette in §2.2.
- No new pages, routes, or functionality — this is a presentation-layer
  rebuild of the existing app.
- No toast/notification system (§5).
- No visual regression/screenshot testing tooling.
- The already-fixed Stage-view stale-speaker bug (see §1) is not part of
  this design's scope — it's independently resolved on `v2` already.
