# Courtroom Web Demo

**Date**: 2026-07-12
**Author**: Noah Scharrenberg
**Project**: psalm-eu v2
**Scope**: A new `examples/web/` demo — a FastAPI backend + React SPA that lets a user configure the courtroom's agents/dimensions, run a trial, watch it unfold live in a courtroom-themed UI driven by the realtime event stream (spec: `2026-07-12-realtime-event-streaming-design.md`), and review/replay the result with full transparency.

---

## 1. Overview

Today, using `psalm` means writing a script (`examples/cli/main.py`) that prints a final JSON blob after the whole evaluation completes. This spec adds a visual, interactive demo that showcases the SDK — including the realtime event stream just built — as a courtroom: the user sets up a case, watches prosecution/defense/judge/jury act out the trial live, and gets a fully transparent, traceable report at the end.

**Explicitly local-only**: one command to run, no auth, no external deployment concerns. One trial runs at a time; starting a second while one is active is rejected with a clear message. This is a demo of the SDK, not a hosted product.

**Explicitly decoupled**: the backend is a thin FastAPI adapter over the existing public `psalm` SDK surface (`PSALM`, `_BuiltPSALM.astream_evaluate()`); the frontend is a fully standalone React SPA that only ever talks to the backend over HTTP + SSE. Neither depends on the other's internals — if this demo is later lifted into its own repository for a production environment, the frontend needs zero changes and the backend is already a clean, minimal API layer.

---

## 2. Architecture & directory layout

```
examples/web/
  backend/
    main.py              # FastAPI app entry point: uv run examples/web/backend/main.py
    catalog.py            # dimension/preset/provider-preset/env-status metadata
    config_resolution.py  # per-agent env-var fallback chain (mirrors examples/cli/main.py)
    trials.py             # trial store, background execution, SSE adapter
    schemas.py             # pydantic request/response models
  frontend/
    src/
      routes/              # Setup, LiveTrial, Results, History
      views/                # TranscriptView, StageView, TimelineView
      state/                # event reducer, Zustand store
      api/                  # typed fetch + EventSource client
    package.json
    vite.config.ts
  README.md
```

**Backend responsibilities**: build a `PSALM` instance from posted config, drive `astream_evaluate()`, buffer events per trial in memory, expose everything over HTTP/SSE. Never renders anything.

**Frontend responsibilities**: render the setup form, the three live-trial views, the results/replay page, and the trial history list. Never talks to the `psalm` package directly — only to the backend's HTTP API.

**Running it:**
- **Demo mode** (default): `npm run build` produces `frontend/dist/`; FastAPI mounts it as static files. `uv run examples/web/backend/main.py` alone serves the whole app on `localhost`.
- **Dev mode**: `npm run dev` (Vite, hot-reload) proxies API/SSE calls to the FastAPI backend running alongside it in a second terminal. Only needed when actively changing the frontend.

---

## 3. Backend API

### 3.1 Endpoints

| Method & Path | Purpose |
|---|---|
| `GET /api/catalog` | Static setup-form metadata (§3.2) |
| `POST /api/trials` | Start a trial (§3.3) |
| `GET /api/trials` | List all trials run this session, newest first (§3.5) |
| `GET /api/trials/{id}` | Trial status/summary + final `PSALMResult` once done |
| `GET /api/trials/{id}/events` | SSE stream: replays buffered backlog, then live events, closes after the terminal event |

### 3.2 `GET /api/catalog`

```json
{
  "dimensions": [
    {
      "name": "Character", "dimension_type": "infringement", "importance": "high",
      "description": "...", "sub_dimensions": [{"name": "...", "description": "...", "importance": "..."}]
    }
    // ... all 9 built-in dimensions from psalm.dimensions.__all__:
    // CHARACTER, PLOT, WORLD_BUILDING, SCENE_SEQUENCE, WRITING_STYLE, NARRATIVE_VOICE
    // (infringement), SCENES_A_FAIRE, CITATIONS, PASTICHE, PARODY_SATIRE (exception)
  ],
  "presets": [
    {"id": "infringing", "label": "Infringing example", "source_text": "...", "target_text": "..."},
    {"id": "not-infringing", "label": "Not-infringing example", "source_text": "...", "target_text": "..."}
  ],
  "evaluation_strategies": [
    {"value": "fully_separate", "label": "Fully separate (default)", "description": "..."},
    {"value": "shared_arg_per_dim_deliberation", "label": "Shared argumentation, per-dimension deliberation", "description": "..."},
    {"value": "shared_all", "label": "Fully shared", "description": "..."}
  ],
  "provider_presets": [
    {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1"},
    {"id": "azure-openai", "label": "Azure OpenAI", "base_url": ""},
    {"id": "together", "label": "Together.ai", "base_url": "https://api.together.xyz/v1"},
    {"id": "groq", "label": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    {"id": "custom", "label": "Local / Custom", "base_url": ""}
  ],
  "env_status": {
    "PSALM_API_KEY": true, "PSALM_BASE_URL": false, "PSALM_MODEL": false,
    "PSALM_PROSECUTOR_API_KEY": false, "PSALM_DEFENSE_API_KEY": false,
    "PSALM_JUDGE_API_KEY": false, "PSALM_JURY_API_KEY": false
    // booleans only — never the values themselves
  }
}
```

`presets` reuses the existing `COPYRIGHT_TEXT`/`INFRINGING_TEXT`/`NOT_INFRINGING_TEXT` constants already defined in `examples/cli/main.py` (imported, not duplicated). The setup form always also allows free-text entry regardless of preset selection.

Voting strategy is **not** user-configurable in this version — the SDK enforces `judge_tiebreaker` must be last (`PSALM-C005`), and the demo always uses the SDK's default chain (`simple_majority` → `trust_weighted` → `judge_tiebreaker`). This is shown as read-only info in the advanced settings section, not an editable list.

### 3.3 `POST /api/trials`

Request body:

```json
{
  "source_text": "...", "target_text": "...",
  "dimensions": ["Character", "Plot"],
  "evaluation_strategy": "fully_separate",
  "argumentation_rounds": 3, "deliberation_rounds": 2, "time_limit_seconds": 120,
  "prosecutor": {"base_url": "", "api_key": "", "model": "", "temperature": 0.7},
  "defense": {"base_url": "...", "api_key": "sk-...", "model": "gpt-4o", "temperature": 0.7},
  "judge": {"base_url": "", "api_key": "", "model": "", "temperature": 0.7},
  "jury": [
    {"base_url": "", "api_key": "", "model": "", "temperature": 0.7, "seed": 0},
    {"base_url": "", "api_key": "", "model": "", "temperature": 0.7, "seed": 1},
    {"base_url": "", "api_key": "", "model": "", "temperature": 0.7, "seed": 2}
  ]
}
```

Any field left blank (`""`) is resolved server-side through the same 3-level fallback chain `examples/cli/main.py` already implements (per-agent env var → jury-wide env var for jurors → global env var). `config_resolution.py` reimplements this logic independently rather than importing it from `examples/cli/main.py` — `examples/` has no `__init__.py` files today (its scripts are standalone, run individually via `uv run python examples/cli/main.py`), and package-ifying it just to share ~20 lines would be unrelated scope creep touching the existing, working CLI example. The two implementations must stay behaviorally identical (same env var names, same fallback order) but are independent code, matching the existing convention of each `examples/` entry being a self-contained script.

Flow:
1. `409 Conflict` if a trial is already running (status `running`).
2. Resolve blanks via the fallback chain; if a required value has no field and no env var, `400` with the same `PSALMConfigError` shape the SDK already raises (code/message/context), attributed to the specific agent.
3. `await PSALM()...build()` — pings every LLM. A failure here (bad key, unreachable endpoint) returns `400` with that agent's `PSALMConfigError`, before any trial starts.
4. On success: generate a `trial_id` (uuid4), start `astream_evaluate()` as a background `asyncio.Task`, append each received event to that trial's in-memory buffer as it arrives. Respond `202 {"trial_id": "..."}` immediately — the caller doesn't wait for the trial to finish.

### 3.4 `GET /api/trials/{id}/events` (SSE)

On connect: write every buffered event for `{id}` as a plain SSE message (`data: <event.model_dump_json()>\n\n`, using the default unnamed `message` event — no custom `event:` name), then keep the connection open and write new events as the background task produces them, then close after writing the terminal event (`FinalVerdictReached` or `RunFailed`). The frontend listens once via `onmessage`, parses the JSON, and switches on its `type` field — the same discriminator already used server-side — rather than registering a listener per event type. A reconnect (browser refresh, flaky connection) after a trial has already progressed sees the same full backlog followed by whatever's still live — nothing is lost, no special resume-token needed, because "replay everything buffered so far" is trivially correct whether the client is connecting for the first time or reconnecting mid-trial.

A comment-line heartbeat (`: keep-alive\n\n`) is sent every 15s of otherwise-silent connection to prevent intermediate proxies/browsers from timing out an idle SSE connection during long LLM calls.

### 3.5 Trial store & history

An in-memory `dict[str, TrialRecord]` on the FastAPI app, session-lifetime only (cleared on restart — no disk persistence). `TrialRecord` holds: `id`, `created_at`, `status` (`running`/`done`/`error`), the resolved config used (for the results page's "trial parameters" section — API keys are never stored in the record, only which agent/model/base_url was used), the event buffer, and the final `PSALMResult` once available. `GET /api/trials` returns a summary list (id, timestamp, source/target text preview, verdict if done, status) sorted newest-first; `GET /api/trials/{id}` returns the full record (minus event buffer, which only the SSE endpoint streams).

---

## 4. Frontend

### 4.1 Routes

| Route | Screen |
|---|---|
| `/` | **Setup** — text input, dimension selection, advanced settings, per-agent config, "Start Trial" |
| `/trial/:id` | **Live Trial** — dimension selector (if 2+ dimensions) + view tabs (Transcript / Stage / Timeline, default Stage) over the live SSE stream |
| `/trial/:id/result` | **Results** — verdict/rationale, full structured report, "Replay" tab reusing the 3 views against buffered history |
| `/trials` | **History** — list of all trials run this session, links to each result page |

### 4.2 Shared event-reducer model

One reducer function, `applyEvent(state, event) -> state`, is the single place that knows how to fold a `PSALMEvent` into derived UI state (current phase/round per dimension, latest speech per role, vote tally, rejected-argument count, closing statements, etc.). Both the **live** consumer (each SSE message calls `applyEvent`) and the **replay** controller (stepping through the buffered array calls `applyEvent` in sequence, at a controllable pace with play/pause/scrub/speed) use this exact same function — replay is guaranteed to look like what was seen live because it's the same code path, not a reimplementation.

All three views (`TranscriptView`, `StageView`, `TimelineView`) are pure presentational components reading this one derived state — they hold no independent state of their own, and switching between them mid-trial is instant (no data loss, no re-fetch).

### 4.3 Multi-dimension handling

When 2+ dimensions are selected, a dimension selector (tabs) sits above the view tabs. It filters which dimension's events feed into `applyEvent`/the derived state for whichever view is currently active — the same filter works identically regardless of which of the 3 views is showing. A small status strip (e.g. "Plot: round 2 · World-Building: deliberation") shows the other dimensions are still progressing in the background. With exactly one dimension selected, the selector is hidden entirely.

### 4.4 The three views (recap from brainstorming)

- **TranscriptView**: scrolling courtroom-transcript log, color-coded by role, auto-scrolls to the newest entry.
- **StageView** (default): a courtroom floor plan — judge bench, prosecutor/defense podiums, jury box — with a speech bubble over whoever is currently acting, and a phase/round indicator.
- **TimelineView**: a phase stepper (Setup → Round 1 → Round 2 → ... → Deliberation → Verdict) on the left, transcript feed for the current phase on the right.

### 4.5 Results page

Verdict + rationale banner, per-dimension score breakdown table, collapsible sections per phase built from the final `PSALMResult` (full argumentation log including every rejected argument with the Judge's stated reason, full deliberation log including every juror's vote/rationale/discussion) — this section reads the already-organized `PSALMResult` structure directly, not the flat event list, since it's already shaped exactly right. A "Replay" tab switches to replaying the buffered raw event list through the same 3 views used live.

### 4.6 Setup form

- **Text input**: preset dropdown (from `/api/catalog`'s `presets`) or free-text source/target fields; selecting a preset fills the fields, which remain editable.
- **Dimensions**: multi-select grouped by `dimension_type` (infringement dimensions checked by default: Character, Plot, World-Building; exception dimensions available but unchecked by default), each showing name/description/importance from the catalog.
- **Advanced settings** (collapsed by default): evaluation strategy dropdown, argumentation/deliberation round counts, time limit — all pre-filled with SDK defaults.
- **Agent config**: one panel each for Prosecutor/Defense/Judge, plus a Jury section with add/remove juror controls (minimum 3, default 3). Each panel: provider preset dropdown (pre-fills `base_url`; "Custom" leaves it editable) + `api_key`/`model`/`temperature` fields. Any field left blank shows "✓ using environment variable" next to it when `/api/catalog`'s `env_status` confirms a fallback exists for that role, or a plain "required" indicator if not.

---

## 5. Error handling

| Failure | Where caught | User-facing result |
|---|---|---|
| Trial already running | `POST /api/trials` | `409`, setup form shows "a trial is already in progress" with a link to watch it |
| Bad/missing API key, unreachable endpoint | `POST /api/trials` → `.build()` | `400` with the failing agent's `PSALMConfigError` code/message, shown inline on that agent's config panel — trial never starts |
| Transient LLM failure mid-trial | Already-built event stream (`AgentCallRetrying`) | Visible live in whichever view is active — a retry is just another courtroom event |
| Fatal failure mid-trial | `RunFailed` event, SSE stream closes | Live/results screens show a clear "Trial failed: `<message>`" state; whatever transcript/log was captured before the failure remains visible, nothing is discarded |
| Browser disconnects/refreshes mid-trial | SSE reconnect on `/trial/:id` | Full backlog replays automatically, then continues live — the run itself was never paused (per the event-streaming spec's "abandoned streams keep running" design) |

---

## 6. Testing

**Backend** (pytest, matching existing `psalm` test conventions):
- Unit tests for `config_resolution.py`'s fallback chain (covers the 3-level precedence directly — `examples/cli/main.py` itself has no automated tests today, only manual verification, so this is new coverage, not a mirror of existing tests).
- Integration tests for `POST /api/trials` → SSE endpoint using FastAPI's `TestClient`, with `PSALM.build()`/`astream_evaluate()` mocked the same way `tests/e2e/test_full_evaluation.py` already mocks agents.
- A test proving SSE reconnection replays the full backlog correctly (connect, receive some events, disconnect, reconnect, confirm backlog + continuation).
- A test proving `409` when starting a second trial while one is running.

**Frontend** (Vitest + React Testing Library):
- Unit tests for `applyEvent` — the single most important piece, since both live and replay depend on it — covering at least one event of each category (lifecycle/argumentation/deliberation/verdict/agent).
- Component tests for each of the 3 views rendering a fixed fake event sequence.
- A test confirming the setup form omits blank fields from the POST payload (so env-var fallback isn't silently defeated by posting empty strings instead of omitting them).

No end-to-end/browser automation is in scope — this is a demo app; manual verification (run it, watch a trial happen) is the acceptance bar, consistent with `examples/cli/main.py` having no automated tests either.

---

## 7. Breaking changes

None. Nothing in the `psalm` package or `examples/cli/main.py` is modified — this is a purely additive new example.

## 8. Files added / modified

| File | Change |
|---|---|
| `examples/web/backend/main.py` | New — FastAPI app, static file mounting for demo mode |
| `examples/web/backend/catalog.py` | New — `/api/catalog` data assembly |
| `examples/web/backend/config_resolution.py` | New — env-var fallback chain (independent reimplementation of the same logic `examples/cli/main.py` already has, per §3.3) |
| `examples/web/backend/trials.py` | New — trial store, background execution, SSE adapter |
| `examples/web/backend/schemas.py` | New — request/response pydantic models |
| `examples/web/frontend/` | New — React + Vite + TypeScript SPA (routes, views, state, api client) |
| `examples/web/README.md` | New — how to run in demo mode and dev mode |
| `pyproject.toml` | Modified — new optional dependency group, e.g. `[project.optional-dependencies].web = ["fastapi", "uvicorn[standard]"]` |

## 9. Unchanged

The `psalm` package's public API, event taxonomy, and orchestration logic are untouched — this is purely a new consumer of `astream_evaluate()`/`with_event_listener()`, built entirely on the existing public surface. `examples/cli/main.py` is untouched.
