# Setup Wizard — Global Agent Defaults

## 1. Overview

Today, `SetupPage`'s Step 3 (Agents) requires configuring Prosecutor,
Defense, Judge, and every juror independently, one collapsed `Accordion`
panel at a time. For the common case — "everything uses the same
provider/model/key" — that's more clicking than necessary. This adds a way
to fill in one configuration once and apply it to every agent at once,
while keeping full per-agent override available exactly as it works today.

**Goal:** a collapsible "Set one configuration for all agents" panel at the
top of Step 3, collapsed by default, with an "Apply to all agents" button
that copies its fields into every agent's config. No backend changes —
the payload sent to start a trial is indistinguishable from a user filling
every agent's fields by hand.

## 2. UI Placement and Structure

Step 3 currently renders one `Accordion` (`multiple`, `defaultValue={[]}`)
containing an `Accordion.Item` per agent (Prosecutor, Defense, Judge, each
juror). This adds a second, separate `Accordion` immediately above it,
with a single, non-multiple `Accordion.Item` labeled "Set one configuration
for all agents", collapsed by default (`defaultValue={null}`). It's a
separate `Accordion` from the per-agent one — not another item mixed into
that list — since it's a bulk action, not another agent.

Its `Accordion.Panel` contains:
- An `AgentConfigPanel` instance (`label="Global defaults"`), reusing the
  exact same component used for every other agent, wired to new
  `globalConfig`/`setGlobalConfig` state (`AgentConfigInput`, same shape as
  `prosecutor`/`defense`/`judge`). Its `envAvailable` prop is
  `catalog.env_status.PSALM_API_KEY` — the generic fallback, since this
  panel isn't scoped to one role.
- A `Button` below it, "Apply to all agents".

## 3. Behavior

Clicking "Apply to all agents" copies `globalConfig`'s `base_url`/
`api_key`/`model`/`temperature` into `prosecutor`, `defense`, `judge`, and
every entry in `jury` at that moment — as if each field had been typed
directly into that agent's own panel. Each juror's `seed` is preserved
(it's unrelated to LLM connection config, not present on the global panel,
and must not be clobbered).

`globalConfig` is not cleared after applying — it stays populated so a
field can be tweaked and "Apply to all agents" clicked again to re-apply.
There is no ongoing link from the global panel to the per-agent ones after
a click: editing any individual agent's panel afterward only overrides
that one agent, exactly like today.

**Edge cases** (decided during design):
- A juror added via "Add juror" *after* "Apply to all agents" was clicked
  starts blank, matching today's `emptyJurorConfig()` behavior — it is
  NOT retroactively included in that earlier apply. Click "Apply to all
  agents" again to include newly-added jurors.
- Clicking "Apply to all agents" while `globalConfig` is entirely blank is
  allowed — it resets every agent back to blank (i.e., back to env-var
  fallback), a legitimate bulk-clear.

## 4. Data Flow

No new data flows to the backend. `handleSubmit`'s `startTrial(...)` call
is unchanged — `prosecutor`/`defense`/`judge`/`jury` are sent exactly as
before; `globalConfig` is pure client-side UI state that never leaves the
browser except by having already been copied into the per-agent state
before submission.

## 5. Error Handling

None needed beyond what exists today. There's no new failure mode — this
is a client-side convenience over state that was already being set one
field at a time.

## 6. Testing

New tests in `SetupPage.test.tsx`:
- The global defaults panel is collapsed by default (its fields aren't
  in the document until expanded) — following the same pattern already
  used for verifying per-agent panels are collapsed by default.
- Filling the global panel and clicking "Apply to all agents" propagates
  the values into Prosecutor, Defense, Judge, and each existing juror
  (verified by expanding a couple of them afterward and checking field
  values) — and does NOT touch a juror's existing `seed`.
- A juror added after "Apply to all agents" was clicked starts blank
  (its fields, once expanded, are empty / show env-var placeholders, not
  the previously-applied values).

No changes needed to `AgentConfigPanel.tsx` itself, its tests, or any
other file.

## 7. Breaking Changes

None. No backend changes. No changes to `startTrial`'s payload shape.

## 8. Files Added / Modified

**Modified:**
- `examples/web/frontend/src/routes/SetupPage.tsx` (new `globalConfig`
  state, new Accordion + Apply-to-all button in Step 3, above the existing
  per-agent Accordion)
- `examples/web/frontend/src/routes/SetupPage.test.tsx` (new tests per §6)

**Unchanged:** everything else — `AgentConfigPanel.tsx`, the backend, the
`psalm` SDK, and every other frontend file.
