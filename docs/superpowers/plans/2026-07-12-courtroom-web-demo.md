# Courtroom Web Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `examples/web/` — a FastAPI backend that adapts `psalm`'s `astream_evaluate()` into a realtime HTTP/SSE API, and a React + Vite + TypeScript SPA that lets a user configure a trial, watch it unfold live in a courtroom-themed UI (three switchable views, driven by the shared event stream), and review/replay the result with full transparency.

**Architecture:** The backend (`examples/web/backend/`) is a thin, standalone adapter over the existing public `psalm` SDK surface — it owns config resolution, an in-memory trial store, and SSE streaming, and never renders anything. The frontend (`examples/web/frontend/`) is a fully decoupled SPA that only ever talks to the backend over HTTP + `EventSource` — never imports `psalm` directly. Both are built backend-first: the backend is independently testable (via `TestClient`/`curl`) before any UI exists.

**Tech Stack:** Backend — FastAPI, `uvicorn[standard]`, Pydantic v2 (existing `psalm` dependency), `pytest` (existing). Frontend — React 18, TypeScript, Vite, React Router, Zustand, Vitest + React Testing Library.

## Global Constraints

- `requires-python = ">=3.14"` (from `pyproject.toml`) — the backend runs under the same interpreter as `psalm` itself.
- Local-only demo: no auth, no external deployment concerns, one trial runs at a time (`409` if a second is started while one is active).
- The backend never stores or logs actual API key values — only which agent/model/base_url was used, and boolean "env var available" flags.
- `examples/` has no package machinery (no `__init__.py` anywhere) — `examples/cli/main.py` and `examples/web/backend/*.py` are independent, standalone script directories. Do NOT introduce cross-imports between them; where logic must be duplicated (the env-var fallback chain, the preset text constants), duplicate it — see spec §3.3 and §3.2.
- Trial history is in-memory only, cleared on backend restart — no database, no disk persistence.
- Voting strategy is not user-configurable — always the SDK's default chain (`simple_majority` → `trust_weighted` → `judge_tiebreaker`).
- `ruff` conventions from the root `pyproject.toml` apply to backend Python code (`select = ["E", "F", "I"]`, line length 100) — run `ruff check examples/web/backend/` before each backend commit.
- Spec reference: `docs/superpowers/specs/2026-07-12-courtroom-web-demo-design.md`. Event-streaming SDK reference: `docs/superpowers/specs/2026-07-12-realtime-event-streaming-design.md`.

---

## Part 1: Backend (FastAPI)

### Task 1: Project scaffolding — `web` extra, directory skeleton, health check

**Files:**
- Modify: `pyproject.toml`
- Create: `examples/web/backend/main.py`
- Create: `examples/web/backend/tests/conftest.py`
- Create: `examples/web/backend/tests/test_main.py`
- Create: `examples/web/README.md`

**Interfaces:**
- Produces: a running FastAPI `app` object in `examples/web/backend/main.py`, importable by later tasks' route modules via flat sibling imports (e.g. `from main import app` is NOT how later tasks will attach routers — instead `main.py` will import an `api_router` from `routes.py` in Task 3+; for now it only needs to exist and serve `GET /api/health`).
- Produces: `examples/web/backend/tests/conftest.py`, which every later backend test file relies on to make flat sibling imports (`import main`, `import trials`, etc.) work under pytest.

- [ ] **Step 1: Add the `web` optional-dependency group**

In `pyproject.toml`, add a new group under `[project.optional-dependencies]` (alongside the existing `dev` group):

```toml
[project.optional-dependencies]
dev = [
    "pytest>=9.1.1",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.15.18",
    "ty>=0.0.51",
]
web = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
]
```

- [ ] **Step 2: Install the new dependency group**

Run: `uv sync --extra dev --extra web`
Expected: resolves and installs `fastapi`, `uvicorn`, and their transitive dependencies with no errors.

- [ ] **Step 3: Write the conftest.py that makes the backend directory importable**

Create `examples/web/backend/tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

This inserts `examples/web/backend/` (the directory containing `main.py`, and every module later tasks add alongside it) onto `sys.path`, so test files in `examples/web/backend/tests/` can do plain `import main`, `import trials`, etc. — matching how `main.py` itself will import its siblings when run directly as a script (Python adds a script's own directory to `sys.path[0]` automatically).

- [ ] **Step 4: Write the failing test for the health check**

Create `examples/web/backend/tests/test_main.py`:

```python
from fastapi.testclient import TestClient

from main import app


def test_health_check_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it fails**

Run: `uv run pytest examples/web/backend/tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 6: Write `main.py`**

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="psalm courtroom demo")

# CORS is only needed in dev mode (Vite's dev server runs on a different port
# than the backend and proxies API calls through the browser's fetch/EventSource,
# which enforces CORS). In demo mode the frontend is served by this same app,
# so no cross-origin requests happen at all — this is a no-op then.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest examples/web/backend/tests/test_main.py -v`
Expected: PASS

- [ ] **Step 8: Verify the app actually starts and serves**

Run: `uv run python examples/web/backend/main.py &` then `curl http://127.0.0.1:8000/api/health`, then stop the background process.
Expected: `{"status":"ok"}`

- [ ] **Step 9: Write the README stub**

Create `examples/web/README.md`:

```markdown
# Courtroom Web Demo

A visual demo of `psalm`: configure a trial, watch it unfold live in a courtroom-themed
UI, review the full transparent result.

## Running (demo mode — one command)

```bash
cd examples/web/frontend && npm install && npm run build && cd ../../..
uv run python examples/web/backend/main.py
```

Open http://127.0.0.1:8000 in a browser.

## Running (dev mode — frontend hot-reload)

Terminal 1:
```bash
uv run python examples/web/backend/main.py
```

Terminal 2:
```bash
cd examples/web/frontend
npm install
npm run dev
```

Open the URL Vite prints (typically http://localhost:5173).

## Configuration

Every agent's `api_key`/`base_url`/`model`/`temperature` can be set directly in the setup
form, or left blank to fall back to the same environment variables `examples/cli/main.py`
uses (see `examples/cli/README.md` for the full fallback-chain reference).
```

(This README will gain more detail in later tasks as the app grows — it's intentionally
minimal for now, just enough to run the health check.)

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock examples/web/
git commit -m "feat: scaffold examples/web backend with health check"
```

---

### Task 2: `config_resolution.py` — env-var fallback chain

**Files:**
- Create: `examples/web/backend/config_resolution.py`
- Create: `examples/web/backend/tests/test_config_resolution.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `resolve_value(posted: str | None, *env_names: str, default: str = "") -> str` — returns `posted` if non-empty, else the first non-empty env var among `env_names`, else `default`.
  - `resolve_agent_config(role_prefix: str, posted: dict) -> dict` — returns `{"base_url": str, "api_key": str, "model": str, "temperature": float}`, resolving each field through `resolve_value`. Raises `ValueError` with a clear message if `api_key` resolves to empty.
  - `resolve_juror_config(index: int, posted: dict) -> dict` — same shape plus `"seed": int`, resolving through the 3-level chain (per-juror → jury-wide → global). Raises `ValueError` if `api_key` resolves to empty.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/backend/tests/test_config_resolution.py`:

```python
import os

import pytest

from config_resolution import resolve_agent_config, resolve_juror_config, resolve_value


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("PSALM_"):
            monkeypatch.delenv(key, raising=False)


def test_resolve_value_prefers_posted_value():
    assert resolve_value("posted", "PSALM_UNUSED") == "posted"


def test_resolve_value_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("PSALM_TEST_VAR", "from-env")
    assert resolve_value(None, "PSALM_TEST_VAR") == "from-env"


def test_resolve_value_falls_back_to_default_when_nothing_set():
    assert resolve_value(None, "PSALM_TEST_VAR", default="fallback") == "fallback"


def test_resolve_value_treats_empty_string_as_unset(monkeypatch):
    monkeypatch.setenv("PSALM_TEST_VAR", "from-env")
    assert resolve_value("", "PSALM_TEST_VAR") == "from-env"


def test_resolve_agent_config_uses_posted_fields():
    cfg = resolve_agent_config(
        "PROSECUTOR",
        {"base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o", "temperature": 0.5},
    )
    assert cfg == {
        "base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o", "temperature": 0.5,
    }


def test_resolve_agent_config_falls_back_to_role_env_var(monkeypatch):
    monkeypatch.setenv("PSALM_PROSECUTOR_API_KEY", "sk-role-env")
    cfg = resolve_agent_config("PROSECUTOR", {})
    assert cfg["api_key"] == "sk-role-env"
    assert cfg["base_url"] == "https://api.openai.com/v1"
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["temperature"] == 0.1


def test_resolve_agent_config_role_env_var_takes_priority_over_global(monkeypatch):
    monkeypatch.setenv("PSALM_API_KEY", "sk-global")
    monkeypatch.setenv("PSALM_PROSECUTOR_API_KEY", "sk-role")
    cfg = resolve_agent_config("PROSECUTOR", {})
    assert cfg["api_key"] == "sk-role"


def test_resolve_agent_config_falls_back_to_global_env_var(monkeypatch):
    monkeypatch.setenv("PSALM_API_KEY", "sk-global")
    cfg = resolve_agent_config("DEFENSE", {})
    assert cfg["api_key"] == "sk-global"


def test_resolve_agent_config_raises_when_no_key_available():
    with pytest.raises(ValueError, match="PROSECUTOR"):
        resolve_agent_config("PROSECUTOR", {})


def test_resolve_juror_config_uses_posted_fields():
    cfg = resolve_juror_config(
        0, {"base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o", "temperature": 0.2, "seed": 7},
    )
    assert cfg == {
        "base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o",
        "temperature": 0.2, "seed": 7,
    }


def test_resolve_juror_config_seed_defaults_to_index():
    cfg = resolve_juror_config(2, {"api_key": "sk"})
    assert cfg["seed"] == 2


def test_resolve_juror_config_per_juror_env_var_takes_priority(monkeypatch):
    monkeypatch.setenv("PSALM_JURY_API_KEY", "sk-jury-wide")
    monkeypatch.setenv("PSALM_JUROR_1_API_KEY", "sk-juror-1")
    cfg0 = resolve_juror_config(0, {})
    cfg1 = resolve_juror_config(1, {})
    assert cfg0["api_key"] == "sk-jury-wide"
    assert cfg1["api_key"] == "sk-juror-1"


def test_resolve_juror_config_falls_back_to_global_env_var(monkeypatch):
    monkeypatch.setenv("PSALM_API_KEY", "sk-global")
    cfg = resolve_juror_config(0, {})
    assert cfg["api_key"] == "sk-global"


def test_resolve_juror_config_raises_when_no_key_available():
    with pytest.raises(ValueError, match="juror 0"):
        resolve_juror_config(0, {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_config_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config_resolution'`

- [ ] **Step 3: Write `config_resolution.py`**

```python
from __future__ import annotations

import os

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = 0.1


def resolve_value(posted: str | None, *env_names: str, default: str = "") -> str:
    if posted:
        return posted
    for name in env_names:
        value = os.getenv(name, "")
        if value:
            return value
    return default


def resolve_agent_config(role_prefix: str, posted: dict) -> dict:
    api_key = resolve_value(
        posted.get("api_key"), f"PSALM_{role_prefix}_API_KEY", "PSALM_API_KEY",
    )
    if not api_key:
        raise ValueError(
            f"No API key provided for {role_prefix} and no "
            f"PSALM_{role_prefix}_API_KEY or PSALM_API_KEY environment variable is set."
        )
    return {
        "base_url": resolve_value(
            posted.get("base_url"), f"PSALM_{role_prefix}_BASE_URL", "PSALM_BASE_URL",
            default=_DEFAULT_BASE_URL,
        ),
        "api_key": api_key,
        "model": resolve_value(
            posted.get("model"), f"PSALM_{role_prefix}_MODEL", "PSALM_MODEL",
            default=_DEFAULT_MODEL,
        ),
        "temperature": float(resolve_value(
            posted.get("temperature") and str(posted["temperature"]),
            f"PSALM_{role_prefix}_TEMPERATURE", "PSALM_TEMPERATURE",
            default=str(_DEFAULT_TEMPERATURE),
        )),
    }


def resolve_juror_config(index: int, posted: dict) -> dict:
    juror_prefix = f"PSALM_JUROR_{index}"
    api_key = resolve_value(
        posted.get("api_key"), f"{juror_prefix}_API_KEY", "PSALM_JURY_API_KEY", "PSALM_API_KEY",
    )
    if not api_key:
        raise ValueError(
            f"No API key provided for juror {index} and no "
            f"{juror_prefix}_API_KEY, PSALM_JURY_API_KEY, or PSALM_API_KEY "
            f"environment variable is set."
        )
    seed = posted.get("seed")
    return {
        "base_url": resolve_value(
            posted.get("base_url"), f"{juror_prefix}_BASE_URL", "PSALM_JURY_BASE_URL", "PSALM_BASE_URL",
            default=_DEFAULT_BASE_URL,
        ),
        "api_key": api_key,
        "model": resolve_value(
            posted.get("model"), f"{juror_prefix}_MODEL", "PSALM_JURY_MODEL", "PSALM_MODEL",
            default=_DEFAULT_MODEL,
        ),
        "temperature": float(resolve_value(
            posted.get("temperature") and str(posted["temperature"]),
            f"{juror_prefix}_TEMPERATURE", "PSALM_JURY_TEMPERATURE", "PSALM_TEMPERATURE",
            default=str(_DEFAULT_TEMPERATURE),
        )),
        "seed": seed if seed is not None else index,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_config_resolution.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Run ruff**

Run: `uv run ruff check examples/web/backend/config_resolution.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/backend/config_resolution.py examples/web/backend/tests/test_config_resolution.py
git commit -m "feat: add env-var fallback chain for web demo agent config"
```

---

### Task 3: `presets.py`, `schemas.py`, `catalog.py`, and `GET /api/catalog`

**Files:**
- Create: `examples/web/backend/presets.py`
- Create: `examples/web/backend/schemas.py`
- Create: `examples/web/backend/catalog.py`
- Create: `examples/web/backend/routes.py`
- Modify: `examples/web/backend/main.py`
- Create: `examples/web/backend/tests/test_catalog.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (this task's tests import `main`/`catalog` directly, relying on Task 1's `tests/conftest.py` for the sibling-import `sys.path` setup).
- Produces:
  - `presets.py`: `COPYRIGHT_TEXT: str`, `INFRINGING_TEXT: str`, `NOT_INFRINGING_TEXT: str`, `PRESETS: list[dict]` (each `{"id", "label", "source_text", "target_text"}`).
  - `schemas.py`: pydantic models `SubDimensionPayload`, `DimensionPayload`, `PresetPayload`, `EvaluationStrategyPayload`, `ProviderPresetPayload`, `CatalogResponse`. Later tasks add more models to this same file.
  - `catalog.py`: `build_catalog() -> CatalogResponse`.
  - `routes.py`: a FastAPI `APIRouter` named `api_router`, with `GET /api/catalog` registered. Later tasks add more routes to this same router.
  - `main.py`: now includes `api_router`.

- [ ] **Step 1: Copy the preset texts from `examples/cli/main.py`**

Open `examples/cli/main.py` and find the three string constants `COPYRIGHT_TEXT` (line 10), `INFRINGING_TEXT` (line 12), and `NOT_INFRINGING_TEXT` (line 14) — each a long Dutch short-story text.

Create `examples/web/backend/presets.py` with those exact three string values, copied verbatim (do not alter a single character — they must byte-for-byte match `examples/cli/main.py`'s constants), under the same names, plus a `PRESETS` list built from them:

```python
COPYRIGHT_TEXT = "<paste the exact value of COPYRIGHT_TEXT from examples/cli/main.py line 10 here>"

INFRINGING_TEXT = "<paste the exact value of INFRINGING_TEXT from examples/cli/main.py line 12 here>"

NOT_INFRINGING_TEXT = "<paste the exact value of NOT_INFRINGING_TEXT from examples/cli/main.py line 14 here>"

PRESETS: list[dict] = [
    {
        "id": "infringing",
        "label": "Infringing example",
        "source_text": COPYRIGHT_TEXT,
        "target_text": INFRINGING_TEXT,
    },
    {
        "id": "not-infringing",
        "label": "Not-infringing example",
        "source_text": COPYRIGHT_TEXT,
        "target_text": NOT_INFRINGING_TEXT,
    },
]
```

- [ ] **Step 2: Write the failing test for the catalog**

Create `examples/web/backend/tests/test_catalog.py`:

```python
from catalog import build_catalog


def test_build_catalog_includes_all_nine_dimensions():
    catalog = build_catalog()
    names = {d.name for d in catalog.dimensions}
    assert names == {
        "Character", "Plot", "World Building", "Scene Sequence", "Writing Style",
        "Narrative Voice", "Scenes a Faire", "Citations", "Pastiche", "Parody Satire",
    } or len(catalog.dimensions) == 9  # exact names verified separately below


def test_build_catalog_dimensions_have_type_and_sub_dimensions():
    catalog = build_catalog()
    for dim in catalog.dimensions:
        assert dim.dimension_type in {"infringement", "exception"}
        assert len(dim.sub_dimensions) > 0
        for sub in dim.sub_dimensions:
            assert sub.name
            assert sub.description


def test_build_catalog_includes_two_presets():
    catalog = build_catalog()
    ids = {p.id for p in catalog.presets}
    assert ids == {"infringing", "not-infringing"}
    for preset in catalog.presets:
        assert preset.source_text
        assert preset.target_text


def test_build_catalog_includes_three_evaluation_strategies():
    catalog = build_catalog()
    values = {s.value for s in catalog.evaluation_strategies}
    assert values == {"fully_separate", "shared_arg_per_dim_deliberation", "shared_all"}


def test_build_catalog_includes_provider_presets():
    catalog = build_catalog()
    ids = {p.id for p in catalog.provider_presets}
    assert "openai" in ids
    assert "custom" in ids


def test_build_catalog_env_status_reflects_actual_environment(monkeypatch):
    monkeypatch.delenv("PSALM_API_KEY", raising=False)
    catalog_without = build_catalog()
    assert catalog_without.env_status["PSALM_API_KEY"] is False

    monkeypatch.setenv("PSALM_API_KEY", "sk-test")
    catalog_with = build_catalog()
    assert catalog_with.env_status["PSALM_API_KEY"] is True
```

**Note on the first test:** the exact `.name` values for each built-in dimension come from `psalm.dimensions` (e.g. `CHARACTER.name`), which may differ from a guessed title-case string — write this test to assert `len(catalog.dimensions) == 9` and that every name is non-empty, rather than guessing exact capitalization, since the actual names are whatever the SDK's `Dimension` objects declare and this task must not hardcode a possibly-wrong guess. Use this simpler version instead:

```python
def test_build_catalog_includes_all_nine_dimensions():
    catalog = build_catalog()
    assert len(catalog.dimensions) == 9
    assert all(d.name for d in catalog.dimensions)
```

(Replace the first test above with this version — it's the one to actually commit.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'catalog'`

- [ ] **Step 4: Write `schemas.py`**

```python
from __future__ import annotations

from pydantic import BaseModel


class SubDimensionPayload(BaseModel):
    name: str
    description: str
    importance: str


class DimensionPayload(BaseModel):
    name: str
    dimension_type: str
    importance: str
    description: str
    sub_dimensions: list[SubDimensionPayload]


class PresetPayload(BaseModel):
    id: str
    label: str
    source_text: str
    target_text: str


class EvaluationStrategyPayload(BaseModel):
    value: str
    label: str
    description: str


class ProviderPresetPayload(BaseModel):
    id: str
    label: str
    base_url: str


class CatalogResponse(BaseModel):
    dimensions: list[DimensionPayload]
    presets: list[PresetPayload]
    evaluation_strategies: list[EvaluationStrategyPayload]
    provider_presets: list[ProviderPresetPayload]
    env_status: dict[str, bool]
```

- [ ] **Step 5: Write `catalog.py`**

```python
from __future__ import annotations

import os

from psalm.dimensions import (
    CHARACTER,
    CITATIONS,
    NARRATIVE_VOICE,
    PARODY_SATIRE,
    PASTICHE,
    PLOT,
    SCENE_SEQUENCE,
    SCENES_A_FAIRE,
    WORLD_BUILDING,
    WRITING_STYLE,
)
from psalm.dimensions.base import Dimension
from psalm.models.config import EvaluationStrategy

from presets import PRESETS
from schemas import (
    CatalogResponse,
    DimensionPayload,
    EvaluationStrategyPayload,
    PresetPayload,
    ProviderPresetPayload,
    SubDimensionPayload,
)

_ALL_DIMENSIONS: list[Dimension] = [
    CHARACTER, PLOT, WORLD_BUILDING, SCENE_SEQUENCE, WRITING_STYLE, NARRATIVE_VOICE,
    SCENES_A_FAIRE, CITATIONS, PASTICHE, PARODY_SATIRE,
]

_EVALUATION_STRATEGY_LABELS: dict[EvaluationStrategy, tuple[str, str]] = {
    EvaluationStrategy.FULLY_SEPARATE: (
        "Fully separate (default)",
        "Each dimension runs its own independent argumentation and deliberation pipeline.",
    ),
    EvaluationStrategy.SHARED_ARG_PER_DIM_DELIBERATION: (
        "Shared argumentation, per-dimension deliberation",
        "One argumentation pass covers all dimensions together; each dimension is deliberated separately.",
    ),
    EvaluationStrategy.SHARED_ALL: (
        "Fully shared",
        "One argumentation pass and one deliberation pass cover all dimensions together.",
    ),
}

_PROVIDER_PRESETS = [
    {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1"},
    {"id": "azure-openai", "label": "Azure OpenAI", "base_url": ""},
    {"id": "together", "label": "Together.ai", "base_url": "https://api.together.xyz/v1"},
    {"id": "groq", "label": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    {"id": "custom", "label": "Local / Custom", "base_url": ""},
]

_ENV_STATUS_KEYS = [
    "PSALM_API_KEY", "PSALM_BASE_URL", "PSALM_MODEL", "PSALM_TEMPERATURE",
    "PSALM_PROSECUTOR_API_KEY", "PSALM_DEFENSE_API_KEY", "PSALM_JUDGE_API_KEY",
    "PSALM_JURY_API_KEY",
]


def _dimension_payload(dim: Dimension) -> DimensionPayload:
    return DimensionPayload(
        name=dim.name,
        dimension_type=dim.dimension_type,
        importance=dim.importance.value,
        description=dim.description,
        sub_dimensions=[
            SubDimensionPayload(name=sd.name, description=sd.description, importance=sd.importance.value)
            for sd in dim.sub_dimensions
        ],
    )


def build_catalog() -> CatalogResponse:
    return CatalogResponse(
        dimensions=[_dimension_payload(d) for d in _ALL_DIMENSIONS],
        presets=[PresetPayload(**p) for p in PRESETS],
        evaluation_strategies=[
            EvaluationStrategyPayload(value=strategy.value, label=label, description=description)
            for strategy, (label, description) in _EVALUATION_STRATEGY_LABELS.items()
        ],
        provider_presets=[ProviderPresetPayload(**p) for p in _PROVIDER_PRESETS],
        env_status={key: bool(os.getenv(key, "")) for key in _ENV_STATUS_KEYS},
    )
```

- [ ] **Step 6: Write `routes.py`**

```python
from __future__ import annotations

from fastapi import APIRouter

from catalog import build_catalog
from schemas import CatalogResponse

api_router = APIRouter(prefix="/api")


@api_router.get("/catalog", response_model=CatalogResponse)
def get_catalog() -> CatalogResponse:
    return build_catalog()
```

- [ ] **Step 7: Wire the router into `main.py`**

Replace the contents of `examples/web/backend/main.py`:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import api_router

app = FastAPI(title="psalm courtroom demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/ -v`
Expected: PASS (all tests from Tasks 1-3)

- [ ] **Step 9: Manually verify the endpoint**

Run: `uv run python examples/web/backend/main.py &` then `curl http://127.0.0.1:8000/api/catalog | head -c 500`, then stop the background process.
Expected: JSON starting with `{"dimensions":[{"name":...`

- [ ] **Step 10: Run ruff**

Run: `uv run ruff check examples/web/backend/`
Expected: no errors

- [ ] **Step 11: Commit**

```bash
git add examples/web/backend/presets.py examples/web/backend/schemas.py examples/web/backend/catalog.py examples/web/backend/routes.py examples/web/backend/main.py examples/web/backend/tests/test_catalog.py
git commit -m "feat: add GET /api/catalog endpoint"
```

---

### Task 4: Trial request/response schemas and the in-memory `TrialStore`

**Files:**
- Modify: `examples/web/backend/schemas.py`
- Create: `examples/web/backend/trials.py`
- Create: `examples/web/backend/tests/test_trials.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces:
  - `schemas.py` additions: `AgentConfigRequest`, `JurorConfigRequest`, `TrialConfigRequest`, `TrialSummary`, `TrialDetail`.
  - `trials.py`: `TrialStatus = Literal["running", "done", "error"]`, `TrialRecord` (dataclass: `id: str`, `created_at: datetime`, `status: TrialStatus`, `source_text: str`, `target_text: str`, `config_summary: dict`, `events: list[dict]`, `result: dict | None`, `error_message: str | None`, `condition: asyncio.Condition`), `TrialStore` (`is_running() -> bool`, `create(source_text, target_text, config_summary) -> TrialRecord`, `get(trial_id) -> TrialRecord | None`, `list_all() -> list[TrialRecord]`, `async append_event(trial_id, event) -> None`, `async mark_done(trial_id, result) -> None`, `async mark_error(trial_id, error_message) -> None`), `trial_summary(record: TrialRecord) -> TrialSummary`, `trial_detail(record: TrialRecord) -> TrialDetail`, and a module-level singleton `store = TrialStore()` that later tasks import and share.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/backend/tests/test_trials.py`:

```python
import asyncio

import pytest

from trials import TrialStore, trial_detail, trial_summary


def test_create_returns_running_record():
    store = TrialStore()
    record = store.create("source", "target", {"prosecutor": {"model": "gpt-4o"}})
    assert record.status == "running"
    assert record.source_text == "source"
    assert record.target_text == "target"
    assert record.events == []
    assert record.result is None


def test_is_running_reflects_current_trial_status():
    store = TrialStore()
    assert store.is_running() is False
    record = store.create("s", "t", {})
    assert store.is_running() is True


async def test_mark_done_stops_is_running():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.mark_done(record.id, {"verdict": "Guilty"})
    assert store.is_running() is False
    assert store.get(record.id).status == "done"
    assert store.get(record.id).result == {"verdict": "Guilty"}


async def test_mark_error_stops_is_running():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.mark_error(record.id, "LLM connection failed")
    assert store.is_running() is False
    assert store.get(record.id).status == "error"
    assert store.get(record.id).error_message == "LLM connection failed"


def test_get_returns_none_for_unknown_id():
    store = TrialStore()
    assert store.get("nonexistent") is None


def test_list_all_returns_newest_first():
    store = TrialStore()
    first = store.create("s1", "t1", {})
    second = store.create("s2", "t2", {})
    ids_in_order = [r.id for r in store.list_all()]
    assert ids_in_order == [second.id, first.id]


async def test_append_event_adds_to_events_list():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.append_event(record.id, {"type": "run_started"})
    assert store.get(record.id).events == [{"type": "run_started"}]


async def test_append_event_wakes_a_waiting_consumer():
    store = TrialStore()
    record = store.create("s", "t", {})

    async def waiter() -> bool:
        async with record.condition:
            await asyncio.wait_for(record.condition.wait(), timeout=2)
        return True

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    await store.append_event(record.id, {"type": "test_event"})
    woke = await asyncio.wait_for(task, timeout=1)
    assert woke is True


def test_trial_summary_previews_texts():
    store = TrialStore()
    record = store.create("a" * 300, "b" * 300, {})
    summary = trial_summary(record)
    assert summary.id == record.id
    assert summary.status == "running"
    assert len(summary.source_text_preview) <= 200
    assert len(summary.target_text_preview) <= 200


def test_trial_detail_includes_config_summary_and_result():
    store = TrialStore()
    record = store.create("s", "t", {"prosecutor": {"model": "gpt-4o"}})
    detail = trial_detail(record)
    assert detail.config_summary == {"prosecutor": {"model": "gpt-4o"}}
    assert detail.result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_trials.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trials'`

- [ ] **Step 3: Add trial schemas to `schemas.py`**

Append to `examples/web/backend/schemas.py`:

```python
from typing import Any


class AgentConfigRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None


class JurorConfigRequest(AgentConfigRequest):
    seed: int | None = None


class TrialConfigRequest(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    evaluation_strategy: str = "fully_separate"
    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 120
    prosecutor: AgentConfigRequest = AgentConfigRequest()
    defense: AgentConfigRequest = AgentConfigRequest()
    judge: AgentConfigRequest = AgentConfigRequest()
    jury: list[JurorConfigRequest] = [
        JurorConfigRequest(), JurorConfigRequest(), JurorConfigRequest(),
    ]


class TrialSummary(BaseModel):
    id: str
    created_at: str
    status: str
    source_text_preview: str
    target_text_preview: str
    verdict: str | None = None
    error_message: str | None = None


class TrialDetail(TrialSummary):
    config_summary: dict[str, Any]
    result: dict[str, Any] | None = None
```

(Move the `from typing import Any` import up to the existing import block at the top of the file rather than leaving it inline — `schemas.py` already has a `from pydantic import BaseModel` line at the top; add `from typing import Any` immediately above it.)

- [ ] **Step 4: Write `trials.py`**

```python
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from schemas import TrialDetail, TrialSummary

TrialStatus = Literal["running", "done", "error"]

_PREVIEW_LENGTH = 200


@dataclass
class TrialRecord:
    id: str
    created_at: datetime
    status: TrialStatus
    source_text: str
    target_text: str
    config_summary: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error_message: str | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition, repr=False)


class TrialStore:
    def __init__(self) -> None:
        self._trials: dict[str, TrialRecord] = {}
        self._current_id: str | None = None

    def is_running(self) -> bool:
        if self._current_id is None:
            return False
        return self._trials[self._current_id].status == "running"

    def create(self, source_text: str, target_text: str, config_summary: dict[str, Any]) -> TrialRecord:
        trial_id = str(uuid.uuid4())
        record = TrialRecord(
            id=trial_id,
            created_at=datetime.now(timezone.utc),
            status="running",
            source_text=source_text,
            target_text=target_text,
            config_summary=config_summary,
        )
        self._trials[trial_id] = record
        self._current_id = trial_id
        return record

    def get(self, trial_id: str) -> TrialRecord | None:
        return self._trials.get(trial_id)

    def list_all(self) -> list[TrialRecord]:
        return sorted(self._trials.values(), key=lambda r: r.created_at, reverse=True)

    async def append_event(self, trial_id: str, event: dict[str, Any]) -> None:
        record = self._trials[trial_id]
        async with record.condition:
            record.events.append(event)
            record.condition.notify_all()

    async def mark_done(self, trial_id: str, result: dict[str, Any]) -> None:
        record = self._trials[trial_id]
        async with record.condition:
            record.status = "done"
            record.result = result
            record.condition.notify_all()

    async def mark_error(self, trial_id: str, error_message: str) -> None:
        record = self._trials[trial_id]
        async with record.condition:
            record.status = "error"
            record.error_message = error_message
            record.condition.notify_all()


def _preview(text: str) -> str:
    return text if len(text) <= _PREVIEW_LENGTH else text[:_PREVIEW_LENGTH]


def trial_summary(record: TrialRecord) -> TrialSummary:
    verdict = record.result.get("verdict") if record.result else None
    return TrialSummary(
        id=record.id,
        created_at=record.created_at.isoformat(),
        status=record.status,
        source_text_preview=_preview(record.source_text),
        target_text_preview=_preview(record.target_text),
        verdict=verdict,
        error_message=record.error_message,
    )


def trial_detail(record: TrialRecord) -> TrialDetail:
    summary = trial_summary(record)
    return TrialDetail(
        **summary.model_dump(),
        config_summary=record.config_summary,
        result=record.result,
    )


store = TrialStore()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_trials.py -v`
Expected: PASS (10 tests)

- [ ] **Step 6: Run ruff**

Run: `uv run ruff check examples/web/backend/`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add examples/web/backend/schemas.py examples/web/backend/trials.py examples/web/backend/tests/test_trials.py
git commit -m "feat: add trial schemas and in-memory TrialStore"
```

---

### Task 5: `POST /api/trials` — resolve config, build PSALM, run in background

**Files:**
- Modify: `examples/web/backend/catalog.py`
- Create: `examples/web/backend/execution.py`
- Modify: `examples/web/backend/routes.py`
- Create: `examples/web/backend/tests/test_execution.py`
- Create: `examples/web/backend/tests/test_routes_trials.py`

**Interfaces:**
- Consumes: `resolve_agent_config`/`resolve_juror_config` (Task 2), `store`/`TrialRecord`/`trial_summary` (Task 4), `TrialConfigRequest` (Task 4).
- Produces:
  - `catalog.py` addition: `resolve_dimensions(names: list[str]) -> list[Dimension]` — raises `ValueError` listing the unknown name if any name isn't in the catalog.
  - `execution.py`: `TrialStartError(Exception)` (`.code: str`, `.message: str`, `.context: dict`), `resolve_config(config: TrialConfigRequest) -> dict` (returns `{"prosecutor": dict, "defense": dict, "judge": dict, "jury": list[dict]}`), `async build_psalm(config: TrialConfigRequest, resolved: dict) -> _BuiltPSALM`, `async run_trial(store: TrialStore, trial_id: str, psalm, source_text: str, target_text: str) -> None`.
  - `routes.py` addition: `POST /api/trials` → `202 {"trial_id": str}` on success, `409` if already running, `400 {"code", "message", "context"}` on a config/build failure.

- [ ] **Step 1: Add `resolve_dimensions` to `catalog.py`**

Add to `examples/web/backend/catalog.py` (after `_ALL_DIMENSIONS`):

```python
_DIMENSION_BY_NAME: dict[str, Dimension] = {d.name: d for d in _ALL_DIMENSIONS}


def resolve_dimensions(names: list[str]) -> list[Dimension]:
    dimensions = []
    for name in names:
        dimension = _DIMENSION_BY_NAME.get(name)
        if dimension is None:
            valid = ", ".join(sorted(_DIMENSION_BY_NAME))
            raise ValueError(f"Unknown dimension: '{name}'. Valid: {valid}")
        dimensions.append(dimension)
    return dimensions
```

- [ ] **Step 2: Write the failing tests for `execution.py`**

Create `examples/web/backend/tests/test_execution.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from schemas import AgentConfigRequest, JurorConfigRequest, TrialConfigRequest
from execution import TrialStartError, build_psalm, resolve_config


def _config(**overrides) -> TrialConfigRequest:
    base = {
        "source_text": "source", "target_text": "target", "dimensions": ["Character"],
        "prosecutor": AgentConfigRequest(api_key="sk-p"),
        "defense": AgentConfigRequest(api_key="sk-d"),
        "judge": AgentConfigRequest(api_key="sk-j"),
        "jury": [JurorConfigRequest(api_key="sk-j0"), JurorConfigRequest(api_key="sk-j1"), JurorConfigRequest(api_key="sk-j2")],
    }
    base.update(overrides)
    return TrialConfigRequest(**base)


def test_resolve_config_resolves_all_roles_and_jury():
    resolved = resolve_config(_config())
    assert resolved["prosecutor"]["api_key"] == "sk-p"
    assert resolved["defense"]["api_key"] == "sk-d"
    assert resolved["judge"]["api_key"] == "sk-j"
    assert len(resolved["jury"]) == 3
    assert resolved["jury"][0]["api_key"] == "sk-j0"


def test_resolve_config_raises_trial_start_error_when_key_missing(monkeypatch):
    for key in ("PSALM_API_KEY", "PSALM_PROSECUTOR_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    config = _config(prosecutor=AgentConfigRequest())
    with pytest.raises(TrialStartError) as exc_info:
        resolve_config(config)
    assert exc_info.value.code == "PSALM-WEB-001"


async def test_build_psalm_raises_trial_start_error_for_unknown_dimension():
    config = _config(dimensions=["NotARealDimension"])
    resolved = resolve_config(config)
    with pytest.raises(TrialStartError) as exc_info:
        await build_psalm(config, resolved)
    assert exc_info.value.code == "PSALM-WEB-002"


async def test_build_psalm_raises_trial_start_error_for_unknown_strategy():
    config = _config(evaluation_strategy="not_a_real_strategy")
    resolved = resolve_config(config)
    with pytest.raises(TrialStartError) as exc_info:
        await build_psalm(config, resolved)
    assert exc_info.value.code == "PSALM-WEB-003"


async def test_build_psalm_returns_built_psalm_on_success():
    config = _config()
    resolved = resolve_config(config)
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        result = await build_psalm(config, resolved)
    assert result is not None
    assert hasattr(result, "astream_evaluate")


async def test_build_psalm_wraps_config_error_from_llm_ping_failure():
    from psalm.exceptions import PSALMConfigError

    config = _config()
    resolved = resolve_config(config)
    ping_failure = AsyncMock(side_effect=PSALMConfigError(
        code="PSALM-C006", message="LLM connection failed for agent 'prosecutor'.", context={"role": "prosecutor"},
    ))
    with patch("psalm.builder.PSALM._ping_llm", new=ping_failure):
        with pytest.raises(TrialStartError) as exc_info:
            await build_psalm(config, resolved)
    assert exc_info.value.code == "PSALM-C006"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_execution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution'`

- [ ] **Step 4: Write `execution.py`**

```python
from __future__ import annotations

from typing import Any

from psalm import PSALM
from psalm.exceptions import PSALMConfigError, PSALMError
from psalm.models.config import EvaluationStrategy

from catalog import resolve_dimensions
from config_resolution import resolve_agent_config, resolve_juror_config
from schemas import TrialConfigRequest
from trials import TrialStore


class TrialStartError(Exception):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.context = context or {}
        super().__init__(message)


def resolve_config(config: TrialConfigRequest) -> dict[str, Any]:
    try:
        prosecutor = resolve_agent_config("PROSECUTOR", config.prosecutor.model_dump())
        defense = resolve_agent_config("DEFENSE", config.defense.model_dump())
        judge = resolve_agent_config("JUDGE", config.judge.model_dump())
        jury = [
            resolve_juror_config(i, juror.model_dump())
            for i, juror in enumerate(config.jury)
        ]
    except ValueError as exc:
        raise TrialStartError(code="PSALM-WEB-001", message=str(exc)) from exc
    return {"prosecutor": prosecutor, "defense": defense, "judge": judge, "jury": jury}


async def build_psalm(config: TrialConfigRequest, resolved: dict[str, Any]):
    try:
        dimensions = resolve_dimensions(config.dimensions)
    except ValueError as exc:
        raise TrialStartError(code="PSALM-WEB-002", message=str(exc)) from exc

    try:
        evaluation_strategy = EvaluationStrategy(config.evaluation_strategy)
    except ValueError as exc:
        raise TrialStartError(
            code="PSALM-WEB-003",
            message=f"Unknown evaluation strategy: '{config.evaluation_strategy}'.",
        ) from exc

    try:
        return await (
            PSALM()
            .with_prosecutor(**resolved["prosecutor"])
            .with_defense(**resolved["defense"])
            .with_judge(**resolved["judge"])
            .with_jury(resolved["jury"])
            .with_dimensions(dimensions)
            .with_debate(
                argumentation_rounds=config.argumentation_rounds,
                deliberation_rounds=config.deliberation_rounds,
                time_limit_seconds=config.time_limit_seconds,
            )
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .with_evaluation_strategy(evaluation_strategy)
            .build()
        )
    except PSALMConfigError as exc:
        raise TrialStartError(code=exc.code, message=exc.message, context=exc.context) from exc


async def run_trial(store: TrialStore, trial_id: str, psalm, source_text: str, target_text: str) -> None:
    try:
        async for event in psalm.astream_evaluate(source_text, target_text):
            await store.append_event(trial_id, event.model_dump(mode="json"))
            if event.type == "final_verdict_reached":
                await store.mark_done(trial_id, event.result.model_dump(mode="json"))
    except PSALMError as exc:
        await store.mark_error(trial_id, exc.message)
    except Exception as exc:  # noqa: BLE001 - any unexpected failure must still surface to the UI
        await store.mark_error(trial_id, str(exc))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_execution.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Write the failing tests for the `POST /api/trials` route**

Create `examples/web/backend/tests/test_routes_trials.py`:

```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from psalm.dimensions.base import Importance
from psalm.models.result import ArgumentationLog, DebateLog, DimensionVerdict, PSALMResult, ResultMetadata
from psalm.events import FinalVerdictReached, RunStarted
from trials import store


def _valid_payload(**overrides) -> dict:
    payload = {
        "source_text": "source text", "target_text": "target text", "dimensions": ["Character"],
        "prosecutor": {"api_key": "sk-p"}, "defense": {"api_key": "sk-d"}, "judge": {"api_key": "sk-j"},
        "jury": [{"api_key": "sk-j0"}, {"api_key": "sk-j1"}, {"api_key": "sk-j2"}],
    }
    payload.update(overrides)
    return payload


def _fake_result() -> PSALMResult:
    return PSALMResult(
        verdict="Guilty", rationale="Because.",
        dimension_verdicts=[
            DimensionVerdict(
                dimension="Character", importance=Importance.HIGH, verdict="Guilty", weighted_score=0.8,
                argumentation_log=ArgumentationLog(rounds=[]),
                debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
            )
        ],
        metadata=ResultMetadata(
            duration_seconds=1.0, argumentation_rounds_used=1, deliberation_rounds_used=1,
            voting_strategy_applied="unanimous",
        ),
    )


def _fake_astream_evaluate(self, source_text, target_text):
    async def _gen():
        yield RunStarted(
            dimensions=["Character"], evaluation_strategy="fully_separate",
            source_length=len(source_text), target_length=len(target_text),
        )
        yield FinalVerdictReached(result=_fake_result())
    return _gen()


def test_post_trials_returns_202_and_trial_id():
    store._trials.clear()
    store._current_id = None
    with (
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
        patch("psalm.builder._BuiltPSALM.astream_evaluate", new=_fake_astream_evaluate),
    ):
        client = TestClient(app)
        response = client.post("/api/trials", json=_valid_payload())
    assert response.status_code == 202
    assert "trial_id" in response.json()


def test_post_trials_runs_trial_and_populates_store():
    store._trials.clear()
    store._current_id = None
    with (
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
        patch("psalm.builder._BuiltPSALM.astream_evaluate", new=_fake_astream_evaluate),
    ):
        client = TestClient(app)
        response = client.post("/api/trials", json=_valid_payload())
        trial_id = response.json()["trial_id"]

    record = store.get(trial_id)
    assert record is not None
    assert record.status == "done"
    assert record.result["verdict"] == "Guilty"
    assert len(record.events) == 2


def test_post_trials_returns_409_when_already_running():
    store._trials.clear()
    store._current_id = None
    store.create("s", "t", {})  # leaves is_running() == True, nothing marks it done

    client = TestClient(app)
    response = client.post("/api/trials", json=_valid_payload())
    assert response.status_code == 409


def test_post_trials_returns_400_when_api_key_missing(monkeypatch):
    store._trials.clear()
    store._current_id = None
    for key in ("PSALM_API_KEY", "PSALM_PROSECUTOR_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(app)
    response = client.post("/api/trials", json=_valid_payload(prosecutor={}))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PSALM-WEB-001"
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_routes_trials.py -v`
Expected: FAIL — `AttributeError` or `404` (no `POST /api/trials` route registered yet)

- [ ] **Step 8: Add the route to `routes.py`**

Replace the contents of `examples/web/backend/routes.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from catalog import build_catalog
from execution import TrialStartError, build_psalm, resolve_config, run_trial
from schemas import CatalogResponse, TrialConfigRequest
from trials import store

api_router = APIRouter(prefix="/api")


@api_router.get("/catalog", response_model=CatalogResponse)
def get_catalog() -> CatalogResponse:
    return build_catalog()


@api_router.post("/trials", status_code=202)
async def start_trial(config: TrialConfigRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    if store.is_running():
        raise HTTPException(status_code=409, detail="A trial is already in progress.")

    try:
        resolved = resolve_config(config)
        psalm = await build_psalm(config, resolved)
    except TrialStartError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message, "context": exc.context},
        ) from exc

    config_summary = {
        "prosecutor": {"model": resolved["prosecutor"]["model"], "base_url": resolved["prosecutor"]["base_url"]},
        "defense": {"model": resolved["defense"]["model"], "base_url": resolved["defense"]["base_url"]},
        "judge": {"model": resolved["judge"]["model"], "base_url": resolved["judge"]["base_url"]},
        "jury": [{"model": j["model"], "base_url": j["base_url"]} for j in resolved["jury"]],
        "dimensions": config.dimensions,
        "evaluation_strategy": config.evaluation_strategy,
    }
    record = store.create(config.source_text, config.target_text, config_summary)
    background_tasks.add_task(run_trial, store, record.id, psalm, config.source_text, config.target_text)
    return {"trial_id": record.id}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_routes_trials.py -v`
Expected: PASS (4 tests)

- [ ] **Step 10: Run the full backend test suite**

Run: `uv run pytest examples/web/backend/tests/ -v`
Expected: PASS (all tests from Tasks 1-5)

- [ ] **Step 11: Run ruff**

Run: `uv run ruff check examples/web/backend/`
Expected: no errors

- [ ] **Step 12: Commit**

```bash
git add examples/web/backend/catalog.py examples/web/backend/execution.py examples/web/backend/routes.py examples/web/backend/tests/test_execution.py examples/web/backend/tests/test_routes_trials.py
git commit -m "feat: add POST /api/trials to build and run trials in the background"
```

---

### Task 6: `GET /api/trials/{id}/events` — SSE streaming with backlog replay

**Files:**
- Create: `examples/web/backend/sse.py`
- Modify: `examples/web/backend/routes.py`
- Create: `examples/web/backend/tests/test_sse.py`

**Interfaces:**
- Consumes: `TrialStore`/`TrialRecord` (Task 4).
- Produces: `sse.py`: `async def stream_trial_events(store: TrialStore, trial_id: str, heartbeat_interval: float = 15.0) -> AsyncIterator[str]` — yields `"data: <json>\n\n"` for every buffered event (in order), then new events as they arrive, then `": keep-alive\n\n"` on idle timeouts, returning once the trial's status is no longer `"running"`. Yields nothing (empty generator) for an unknown `trial_id`.
- `routes.py` addition: `GET /api/trials/{trial_id}/events` → `200` streaming `text/event-stream`, or `404` if the trial doesn't exist.

- [ ] **Step 1: Write the failing tests for `sse.py`**

Create `examples/web/backend/tests/test_sse.py`:

```python
import asyncio
import json

from sse import stream_trial_events
from trials import TrialStore


async def test_stream_replays_backlog_immediately():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.append_event(record.id, {"type": "run_started"})
    await store.append_event(record.id, {"type": "final_verdict_reached"})
    await store.mark_done(record.id, {"verdict": "Guilty"})

    messages = [msg async for msg in stream_trial_events(store, record.id) if msg.startswith("data: ")]
    parsed = [json.loads(m[len("data: "):]) for m in messages]
    assert parsed == [{"type": "run_started"}, {"type": "final_verdict_reached"}]


async def test_stream_yields_new_events_as_they_arrive():
    store = TrialStore()
    record = store.create("s", "t", {})

    async def producer() -> None:
        await asyncio.sleep(0.05)
        await store.append_event(record.id, {"type": "run_started"})
        await asyncio.sleep(0.05)
        await store.mark_done(record.id, {"verdict": "Guilty"})

    producer_task = asyncio.create_task(producer())
    collected = [msg async for msg in stream_trial_events(store, record.id) if msg.startswith("data: ")]
    await producer_task
    parsed = [json.loads(m[len("data: "):]) for m in collected]
    assert parsed == [{"type": "run_started"}]


async def test_stream_sends_heartbeat_when_idle():
    store = TrialStore()
    record = store.create("s", "t", {})

    async def eventually_finish() -> None:
        await asyncio.sleep(0.3)
        await store.mark_done(record.id, {"verdict": "Guilty"})

    asyncio.create_task(eventually_finish())
    messages = [msg async for msg in stream_trial_events(store, record.id, heartbeat_interval=0.05)]
    assert any(m.startswith(": keep-alive") for m in messages)


async def test_stream_returns_nothing_for_unknown_trial():
    store = TrialStore()
    messages = [msg async for msg in stream_trial_events(store, "nonexistent")]
    assert messages == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_sse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sse'`

- [ ] **Step 3: Write `sse.py`**

```python
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from trials import TrialStore


async def stream_trial_events(
    store: TrialStore, trial_id: str, heartbeat_interval: float = 15.0
) -> AsyncIterator[str]:
    record = store.get(trial_id)
    if record is None:
        return

    index = 0
    while True:
        while index < len(record.events):
            yield f"data: {json.dumps(record.events[index])}\n\n"
            index += 1
        if record.status != "running":
            return
        async with record.condition:
            if index >= len(record.events) and record.status == "running":
                try:
                    await asyncio.wait_for(record.condition.wait(), timeout=heartbeat_interval)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
```

The `async with record.condition:` block re-checks the "anything new yet?" predicate *while holding the lock* before waiting — `append_event`/`mark_done`/`mark_error` (Task 4) all acquire the same lock before mutating and notifying, so there's no window where an event could be appended and its notification missed between this generator's last check and the moment it starts waiting.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_sse.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the failing tests for the HTTP route**

Append to `examples/web/backend/tests/test_routes_trials.py`:

```python
import asyncio

from trials import store as _store  # already imported as `store` above; alias avoids shadowing


def test_get_trial_events_endpoint_streams_backlog_for_done_trial():
    store._trials.clear()
    store._current_id = None
    record = store.create("s", "t", {})
    asyncio.run(store.append_event(record.id, {"type": "run_started"}))
    asyncio.run(store.mark_done(record.id, {"verdict": "Guilty"}))

    client = TestClient(app)
    with client.stream("GET", f"/api/trials/{record.id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "run_started" in body


def test_get_trial_events_endpoint_404s_for_unknown_trial():
    client = TestClient(app)
    response = client.get("/api/trials/nonexistent/events")
    assert response.status_code == 404
```

(The `import asyncio` and the `_store` alias import are only needed if not already present at the top of the file from Task 5 — check first; if `store` is already imported there, just add `import asyncio` and skip the alias, using `store` directly.)

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_routes_trials.py -v -k events`
Expected: FAIL — `404` (no route registered yet)

- [ ] **Step 7: Add the route to `routes.py`**

Add to `examples/web/backend/routes.py` (imports: add `from fastapi.responses import StreamingResponse` and `from sse import stream_trial_events`; route: add after `start_trial`):

```python
@api_router.get("/trials/{trial_id}/events")
async def stream_events(trial_id: str):
    if store.get(trial_id) is None:
        raise HTTPException(status_code=404, detail="Trial not found.")
    return StreamingResponse(stream_trial_events(store, trial_id), media_type="text/event-stream")
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_routes_trials.py -v`
Expected: PASS (6 tests)

- [ ] **Step 9: Run the full backend test suite and ruff**

Run: `uv run pytest examples/web/backend/tests/ -v && uv run ruff check examples/web/backend/`
Expected: all PASS, no lint errors

- [ ] **Step 10: Commit**

```bash
git add examples/web/backend/sse.py examples/web/backend/routes.py examples/web/backend/tests/test_sse.py examples/web/backend/tests/test_routes_trials.py
git commit -m "feat: add SSE endpoint with backlog replay and heartbeat"
```

---

### Task 7: `GET /api/trials` and `GET /api/trials/{id}` — history and detail

**Files:**
- Modify: `examples/web/backend/routes.py`
- Create: `examples/web/backend/tests/test_routes_list.py`

**Interfaces:**
- Consumes: `store`, `trial_summary`, `trial_detail` (Task 4).
- Produces: `routes.py` additions: `GET /api/trials` → `200 list[TrialSummary]` (newest first), `GET /api/trials/{trial_id}` → `200 TrialDetail` or `404`.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/backend/tests/test_routes_list.py`:

```python
from fastapi.testclient import TestClient

from main import app
from trials import store


def test_list_trials_returns_empty_list_initially():
    store._trials.clear()
    store._current_id = None
    client = TestClient(app)
    response = client.get("/api/trials")
    assert response.status_code == 200
    assert response.json() == []


def test_list_trials_returns_newest_first():
    store._trials.clear()
    store._current_id = None
    first = store.create("s1", "t1", {})
    second = store.create("s2", "t2", {})

    client = TestClient(app)
    response = client.get("/api/trials")
    ids = [t["id"] for t in response.json()]
    assert ids == [second.id, first.id]


def test_get_trial_returns_detail():
    store._trials.clear()
    store._current_id = None
    record = store.create("source", "target", {"prosecutor": {"model": "gpt-4o"}})

    client = TestClient(app)
    response = client.get(f"/api/trials/{record.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == record.id
    assert body["status"] == "running"
    assert body["config_summary"] == {"prosecutor": {"model": "gpt-4o"}}


def test_get_trial_returns_404_for_unknown_id():
    client = TestClient(app)
    response = client.get("/api/trials/nonexistent")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest examples/web/backend/tests/test_routes_list.py -v`
Expected: FAIL — `404` (routes not registered yet)

- [ ] **Step 3: Add the routes to `routes.py`**

Add to `examples/web/backend/routes.py` (imports: add `TrialDetail`, `TrialSummary` to the existing `from schemas import ...` line; add `trial_detail`, `trial_summary` to the existing `from trials import ...` line; routes: add after `start_trial`, before `stream_events`):

```python
@api_router.get("/trials", response_model=list[TrialSummary])
def list_trials() -> list[TrialSummary]:
    return [trial_summary(r) for r in store.list_all()]


@api_router.get("/trials/{trial_id}", response_model=TrialDetail)
def get_trial(trial_id: str) -> TrialDetail:
    record = store.get(trial_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Trial not found.")
    return trial_detail(record)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest examples/web/backend/tests/test_routes_list.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full backend test suite, ruff, and `ty`**

Run:
```bash
uv run pytest examples/web/backend/tests/ -v
uv run ruff check examples/web/backend/
```
Expected: all PASS, no lint errors. This is the last backend-only task — the backend is now feature-complete per the spec's §3 API surface and independently usable via `curl`/`TestClient` even with no frontend.

- [ ] **Step 6: Manually verify the full backend flow end-to-end**

With a real (or test/throwaway) OpenAI-compatible API key:

```bash
export PSALM_API_KEY="sk-..."
uv run python examples/web/backend/main.py &
curl http://127.0.0.1:8000/api/catalog | head -c 200
curl -X POST http://127.0.0.1:8000/api/trials -H "Content-Type: application/json" -d '{
  "source_text": "A wizard with blue eyes cast a spell.",
  "target_text": "A sorcerer with striking azure eyes conjured magic.",
  "dimensions": ["Character"],
  "prosecutor": {}, "defense": {}, "judge": {}, "jury": [{}, {}, {}]
}'
# note the returned trial_id, then:
curl http://127.0.0.1:8000/api/trials/<trial_id>/events
curl http://127.0.0.1:8000/api/trials/<trial_id>
curl http://127.0.0.1:8000/api/trials
kill %1
```

Expected: catalog JSON, a `trial_id`, an SSE stream of events ending in `final_verdict_reached`, a detail response with `status: "done"` and a full `result`, and a one-item history list.

- [ ] **Step 7: Commit**

```bash
git add examples/web/backend/routes.py examples/web/backend/tests/test_routes_list.py
git commit -m "feat: add GET /api/trials and GET /api/trials/{id} history endpoints"
```

---

## Part 2: Frontend (React + Vite + TypeScript)

The backend from Part 1 is now complete and independently testable. This part builds the SPA on top of it — nothing here touches `examples/web/backend/` or the `psalm` package.

### Task 8: Vite + React + TypeScript + Vitest scaffolding

**Files:**
- Create: `examples/web/frontend/package.json`
- Create: `examples/web/frontend/tsconfig.json`
- Create: `examples/web/frontend/tsconfig.node.json`
- Create: `examples/web/frontend/vite.config.ts`
- Create: `examples/web/frontend/index.html`
- Create: `examples/web/frontend/.gitignore`
- Create: `examples/web/frontend/src/main.tsx`
- Create: `examples/web/frontend/src/App.tsx`
- Create: `examples/web/frontend/src/App.test.tsx`
- Create: `examples/web/frontend/src/index.css`
- Create: `examples/web/frontend/src/test/setup.ts`

**Interfaces:**
- Consumes: nothing (this task establishes the frontend project itself).
- Produces: a working Vite dev server (proxying `/api/*` to `http://127.0.0.1:8000` for dev mode), a working `npm run build`, and a working `npm run test` (Vitest + jsdom + React Testing Library) — the foundation every later frontend task builds on.

- [ ] **Step 1: Write `package.json`**

Create `examples/web/frontend/package.json`:

```json
{
  "name": "psalm-courtroom-web-demo",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "zustand": "^4.5.4"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.8",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^24.1.1",
    "typescript": "^5.5.4",
    "vite": "^5.4.0",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json` and `tsconfig.node.json`**

Create `examples/web/frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `examples/web/frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 3: Write `vite.config.ts`**

Create `examples/web/frontend/vite.config.ts`:

```typescript
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

The `server.proxy` entry is what makes dev mode work: Vite's dev server (port 5173) forwards any `/api/*` request — including the SSE endpoint, since proxying works for streaming responses too — to the FastAPI backend on port 8000, so the frontend code never needs to know which port it's actually talking to.

- [ ] **Step 4: Write `index.html`, `.gitignore`, and the CSS/setup files**

Create `examples/web/frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>psalm courtroom demo</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `examples/web/frontend/.gitignore`:

```
node_modules
dist
```

Create `examples/web/frontend/src/test/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

Create `examples/web/frontend/src/index.css`:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: #0f1115;
  color: #e6e6e6;
}
```

- [ ] **Step 5: Write `main.tsx` and a minimal `App.tsx`**

Create `examples/web/frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Create `examples/web/frontend/src/App.tsx`:

```tsx
export default function App() {
  return <div>psalm courtroom demo</div>;
}
```

(`App.tsx` is replaced with real routing in Task 20 — this placeholder exists only to prove the toolchain works end-to-end.)

- [ ] **Step 6: Write the smoke test**

Create `examples/web/frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders without crashing", () => {
    render(<App />);
    expect(screen.getByText(/psalm courtroom demo/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Install dependencies**

Run: `cd examples/web/frontend && npm install`
Expected: installs with no errors, creates `node_modules/` and `package-lock.json`.

- [ ] **Step 8: Run the test suite**

Run: `cd examples/web/frontend && npm run test`
Expected: `1 passed`

- [ ] **Step 9: Verify the dev server starts**

Run: `cd examples/web/frontend && npm run dev` (in the background), then in another terminal `curl -s http://localhost:5173 | grep -o "<title>.*</title>"`, then stop the dev server.
Expected: `<title>psalm courtroom demo</title>`

- [ ] **Step 10: Verify the production build works**

Run: `cd examples/web/frontend && npm run build`
Expected: completes with no TypeScript errors, produces `examples/web/frontend/dist/index.html` and bundled JS/CSS assets.

- [ ] **Step 11: Commit**

```bash
git add examples/web/frontend/package.json examples/web/frontend/package-lock.json examples/web/frontend/tsconfig.json examples/web/frontend/tsconfig.node.json examples/web/frontend/vite.config.ts examples/web/frontend/index.html examples/web/frontend/.gitignore examples/web/frontend/src/
git commit -m "feat: scaffold Vite + React + TypeScript + Vitest frontend"
```

---

### Task 9: TypeScript types — backend schemas + the `PSALMEvent` discriminated union

**Files:**
- Create: `examples/web/frontend/src/api/types.ts`
- Create: `examples/web/frontend/src/api/types.test.ts`

**Interfaces:**
- Consumes: the exact shapes from `examples/web/backend/schemas.py` (Tasks 3-4) and the SDK's event taxonomy (`docs/superpowers/specs/2026-07-12-realtime-event-streaming-design.md` §3) and result models (`psalm/models/result.py`, `psalm/models/evidence.py`).
- Produces: every type every later frontend task imports from `"../api/types"` (or `"./types"` from within `src/api/`): `SubDimension`, `DimensionCatalogEntry`, `Preset`, `EvaluationStrategyOption`, `ProviderPreset`, `CatalogResponse`, `AgentConfigInput`, `JurorConfigInput`, `TrialConfigInput`, `TrialSummary`, `TrialDetail`, `Proof`, `Argument`, `RejectedArgument`, `DimensionScore`, `JurorVote`, `RoundArguments`, `RoundDeliberation`, `ArgumentationLog`, `DebateLog`, `DimensionVerdict`, `ResultMetadata`, `PSALMResult`, and the `PSALMEvent` discriminated union (all 20 member types, each individually exported).

- [ ] **Step 1: Write `types.ts`**

Create `examples/web/frontend/src/api/types.ts`:

```typescript
// --- Catalog (mirrors examples/web/backend/schemas.py's CatalogResponse family) ---

export interface SubDimension {
  name: string;
  description: string;
  importance: string;
}

export interface DimensionCatalogEntry {
  name: string;
  dimension_type: "infringement" | "exception";
  importance: string;
  description: string;
  sub_dimensions: SubDimension[];
}

export interface Preset {
  id: string;
  label: string;
  source_text: string;
  target_text: string;
}

export interface EvaluationStrategyOption {
  value: "fully_separate" | "shared_arg_per_dim_deliberation" | "shared_all";
  label: string;
  description: string;
}

export interface ProviderPreset {
  id: string;
  label: string;
  base_url: string;
}

export interface CatalogResponse {
  dimensions: DimensionCatalogEntry[];
  presets: Preset[];
  evaluation_strategies: EvaluationStrategyOption[];
  provider_presets: ProviderPreset[];
  env_status: Record<string, boolean>;
}

// --- Trial request (mirrors TrialConfigRequest / AgentConfigRequest / JurorConfigRequest) ---

export interface AgentConfigInput {
  base_url?: string;
  api_key?: string;
  model?: string;
  temperature?: number;
}

export interface JurorConfigInput extends AgentConfigInput {
  seed?: number;
}

export interface TrialConfigInput {
  source_text: string;
  target_text: string;
  dimensions: string[];
  evaluation_strategy: string;
  argumentation_rounds: number;
  deliberation_rounds: number;
  time_limit_seconds: number;
  prosecutor: AgentConfigInput;
  defense: AgentConfigInput;
  judge: AgentConfigInput;
  jury: JurorConfigInput[];
}

// --- Trial response (mirrors TrialSummary / TrialDetail) ---

export interface TrialSummary {
  id: string;
  created_at: string;
  status: "running" | "done" | "error";
  source_text_preview: string;
  target_text_preview: string;
  verdict: string | null;
  error_message: string | null;
}

export interface TrialDetail extends TrialSummary {
  config_summary: Record<string, unknown>;
  result: PSALMResult | null;
}

// --- Result shapes (mirrors psalm/models/evidence.py and psalm/models/result.py) ---

export interface Proof {
  source_excerpt: string;
  target_excerpt: string;
  relevance: string;
}

export interface Argument {
  claim: string;
  dimension: string;
  proofs: Proof[];
  agent_role: string;
  round: number;
}

export interface RejectedArgument {
  argument: Argument;
  rejection_reason: string;
}

export interface DimensionScore {
  sub_dimension: string;
  score: "none" | "generic" | "possible" | "clear";
  reasoning: string;
}

export interface JurorVote {
  juror_id: string;
  vote: "Guilty" | "Not Guilty" | "Undecided";
  rationale: string;
  dimension_scores: DimensionScore[];
  dimension: string | null;
}

export interface RoundArguments {
  round: number;
  prosecution_arguments: Argument[];
  prosecution_rejected_arguments: RejectedArgument[];
  prosecution_closing_statement: string | null;
  defense_counters: Argument[];
  defense_counter_rejected_arguments: RejectedArgument[];
  defense_counter_closing_statement: string | null;
  defense_arguments: Argument[];
  defense_rejected_arguments: RejectedArgument[];
  defense_closing_statement: string | null;
  prosecution_counters: Argument[];
  prosecution_counter_rejected_arguments: RejectedArgument[];
  prosecution_counter_closing_statement: string | null;
}

export interface RoundDeliberation {
  round: number;
  discussion_messages: { juror_id: string; message: string }[];
  votes: JurorVote[];
  aggregated_result: string | null;
}

export interface ArgumentationLog {
  rounds: RoundArguments[];
  prosecution_closing_argument: string | null;
  defense_closing_argument: string | null;
}

export interface DebateLog {
  rounds: RoundDeliberation[];
  final_voting_strategy_applied: string;
}

export interface DimensionVerdict {
  dimension: string;
  dimension_type: "infringement" | "exception";
  importance: string;
  verdict: "Guilty" | "Not Guilty" | "Undecided";
  weighted_score: number;
  argumentation_log: ArgumentationLog;
  debate_log: DebateLog;
}

export interface ResultMetadata {
  duration_seconds: number;
  argumentation_rounds_used: number;
  deliberation_rounds_used: number;
  voting_strategy_applied: string;
  agent_failures: unknown[];
}

export interface PSALMResult {
  verdict: "Guilty" | "Not Guilty" | "Undecided";
  rationale: string;
  dimension_verdicts: DimensionVerdict[];
  metadata: ResultMetadata;
}

// --- Event envelope + discriminated union (mirrors psalm/events/types.py) ---

interface EventEnvelope {
  event_id: string;
  sequence: number;
  timestamp: string;
  run_id: string;
  dimension: string | null;
}

export interface RunStarted extends EventEnvelope {
  category: "lifecycle";
  type: "run_started";
  dimensions: string[];
  evaluation_strategy: string;
  source_length: number;
  target_length: number;
}

export interface RunFailed extends EventEnvelope {
  category: "lifecycle";
  type: "run_failed";
  code: string;
  message: string;
  context: Record<string, unknown>;
}

export interface DimensionStarted extends EventEnvelope {
  category: "lifecycle";
  type: "dimension_started";
  dimension_type: string;
  importance: string;
}

export interface ArgumentationRoundStarted extends EventEnvelope {
  category: "argumentation";
  type: "argumentation_round_started";
  round: number;
}

export interface ArgumentSubmitted extends EventEnvelope {
  category: "argumentation";
  type: "argument_submitted";
  round: number;
  role: "prosecution" | "defense";
  kind: "argument" | "counter";
  argument: Argument;
}

export interface ArgumentValidated extends EventEnvelope {
  category: "argumentation";
  type: "argument_validated";
  round: number;
  role: string;
  argument: Argument;
}

export interface ArgumentRejected extends EventEnvelope {
  category: "argumentation";
  type: "argument_rejected";
  round: number;
  role: string;
  argument: Argument;
  reason: string;
}

export interface ClosingStatementDelivered extends EventEnvelope {
  category: "argumentation";
  type: "closing_statement_delivered";
  round: number;
  role: string;
  statement: string;
}

export interface ArgumentationStabilityChecked extends EventEnvelope {
  category: "argumentation";
  type: "argumentation_stability_checked";
  round: number;
  stability_detected: boolean;
}

export interface ClosingArgumentDelivered extends EventEnvelope {
  category: "argumentation";
  type: "closing_argument_delivered";
  role: string;
  statement: string;
}

export interface ArgumentBatchCompletenessRetry extends EventEnvelope {
  category: "argumentation";
  type: "argument_batch_completeness_retry";
  round: number;
  role: string;
  attempt: number;
  max_attempts: number;
}

export interface DeliberationRoundStarted extends EventEnvelope {
  category: "deliberation";
  type: "deliberation_round_started";
  round: number;
}

export interface JurorVoteCast extends EventEnvelope {
  category: "deliberation";
  type: "juror_vote_cast";
  round: number;
  juror_id: string;
  vote: string;
  rationale: string;
  dimension_scores: DimensionScore[];
}

export interface JuryConsensusChecked extends EventEnvelope {
  category: "deliberation";
  type: "jury_consensus_checked";
  round: number;
  is_unanimous: boolean;
  top_verdict: string | null;
}

export interface JuryDiscussionMessage extends EventEnvelope {
  category: "deliberation";
  type: "jury_discussion_message";
  round: number;
  juror_id: string;
  message: string;
}

export interface VotingStrategyApplied extends EventEnvelope {
  category: "deliberation";
  type: "voting_strategy_applied";
  strategy_name: string;
  is_tie: boolean;
  verdict: string | null;
}

export interface DimensionVerdictReached extends EventEnvelope {
  category: "verdict";
  type: "dimension_verdict_reached";
  dimension_type: string;
  importance: string;
  verdict: string;
  weighted_score: number;
}

export interface FinalVerdictReached extends EventEnvelope {
  category: "verdict";
  type: "final_verdict_reached";
  result: PSALMResult;
}

export interface AgentCallRetrying extends EventEnvelope {
  category: "agent";
  type: "agent_call_retrying";
  role: string;
  attempt: number;
  max_attempts: number;
  backoff_seconds: number;
  error: string;
}

export interface AgentCallFailed extends EventEnvelope {
  category: "agent";
  type: "agent_call_failed";
  role: string;
  attempts: number;
  code: string;
  error: string;
}

export type PSALMEvent =
  | RunStarted
  | RunFailed
  | DimensionStarted
  | ArgumentationRoundStarted
  | ArgumentSubmitted
  | ArgumentValidated
  | ArgumentRejected
  | ClosingStatementDelivered
  | ArgumentationStabilityChecked
  | ClosingArgumentDelivered
  | ArgumentBatchCompletenessRetry
  | DeliberationRoundStarted
  | JurorVoteCast
  | JuryConsensusChecked
  | JuryDiscussionMessage
  | VotingStrategyApplied
  | DimensionVerdictReached
  | FinalVerdictReached
  | AgentCallRetrying
  | AgentCallFailed;
```

- [ ] **Step 2: Write a compile-time + runtime sanity test**

Create `examples/web/frontend/src/api/types.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { PSALMEvent, RunStarted, FinalVerdictReached } from "./types";

function narrowByType(event: PSALMEvent): string {
  // Exercises that TypeScript can discriminate the union purely on `.type`,
  // and that every member is actually reachable from the union type.
  switch (event.type) {
    case "run_started":
      return `dimensions:${event.dimensions.length}`;
    case "final_verdict_reached":
      return `verdict:${event.result.verdict}`;
    default:
      return event.type;
  }
}

describe("PSALMEvent discriminated union", () => {
  it("narrows RunStarted correctly by its literal type", () => {
    const event: RunStarted = {
      event_id: "1", sequence: 1, timestamp: "2026-01-01T00:00:00Z", run_id: "r1", dimension: null,
      category: "lifecycle", type: "run_started",
      dimensions: ["Character", "Plot"], evaluation_strategy: "fully_separate",
      source_length: 10, target_length: 12,
    };
    expect(narrowByType(event)).toBe("dimensions:2");
  });

  it("narrows FinalVerdictReached correctly by its literal type", () => {
    const event: FinalVerdictReached = {
      event_id: "2", sequence: 2, timestamp: "2026-01-01T00:00:01Z", run_id: "r1", dimension: null,
      category: "verdict", type: "final_verdict_reached",
      result: {
        verdict: "Guilty", rationale: "Because.", dimension_verdicts: [],
        metadata: {
          duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
          voting_strategy_applied: "unanimous", agent_failures: [],
        },
      },
    };
    expect(narrowByType(event)).toBe("verdict:Guilty");
  });
});
```

- [ ] **Step 3: Run the test suite**

Run: `cd examples/web/frontend && npm run test`
Expected: `3 passed` (the `App` smoke test from Task 8 plus these 2)

- [ ] **Step 4: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add examples/web/frontend/src/api/types.ts examples/web/frontend/src/api/types.test.ts
git commit -m "feat: add TypeScript types for backend schemas and the PSALMEvent union"
```

---

### Task 10: `api/client.ts` — typed fetch wrappers and the SSE helper

**Files:**
- Create: `examples/web/frontend/src/api/client.ts`
- Create: `examples/web/frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: every type from `examples/web/frontend/src/api/types.ts` (Task 9).
- Produces: `getCatalog(): Promise<CatalogResponse>`, `startTrial(config: TrialConfigInput): Promise<{trial_id: string}>` (throws `TrialConflictError` on 409, `TrialConfigError` — with `.code`, `.message`, `.context` — on 400), `getTrial(id: string): Promise<TrialDetail>`, `listTrials(): Promise<TrialSummary[]>`, `openTrialEventStream(id: string, onEvent: (event: PSALMEvent) => void, onClose?: () => void): () => void` (the returned function closes the connection early).

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/api/client.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  TrialConfigError,
  TrialConflictError,
  getCatalog,
  getTrial,
  listTrials,
  openTrialEventStream,
  startTrial,
} from "./client";
import type { TrialConfigInput } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

const sampleConfig: TrialConfigInput = {
  source_text: "s", target_text: "t", dimensions: ["Character"], evaluation_strategy: "fully_separate",
  argumentation_rounds: 3, deliberation_rounds: 2, time_limit_seconds: 120,
  prosecutor: {}, defense: {}, judge: {}, jury: [],
};

describe("getCatalog", () => {
  it("fetches and parses the catalog", async () => {
    const fakeCatalog = { dimensions: [], presets: [], evaluation_strategies: [], provider_presets: [], env_status: {} };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => fakeCatalog }));
    const result = await getCatalog();
    expect(result).toEqual(fakeCatalog);
    expect(fetch).toHaveBeenCalledWith("/api/catalog");
  });
});

describe("startTrial", () => {
  it("returns the trial_id on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 202, json: async () => ({ trial_id: "abc" }) }));
    const result = await startTrial(sampleConfig);
    expect(result).toEqual({ trial_id: "abc" });
  });

  it("throws TrialConflictError on 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409 }));
    await expect(startTrial(sampleConfig)).rejects.toBeInstanceOf(TrialConflictError);
  });

  it("throws TrialConfigError with code/message/context on 400", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 400,
      json: async () => ({ detail: { code: "PSALM-WEB-001", message: "No API key", context: {} } }),
    }));
    const error = await startTrial(sampleConfig).catch((e) => e);
    expect(error).toBeInstanceOf(TrialConfigError);
    expect(error.code).toBe("PSALM-WEB-001");
    expect(error.message).toBe("No API key");
  });
});

describe("getTrial", () => {
  it("fetches trial detail by id", async () => {
    const fakeDetail = { id: "abc", status: "done" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => fakeDetail }));
    const result = await getTrial("abc");
    expect(result).toEqual(fakeDetail);
    expect(fetch).toHaveBeenCalledWith("/api/trials/abc");
  });
});

describe("listTrials", () => {
  it("fetches the trial history list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    const result = await listTrials();
    expect(result).toEqual([]);
  });
});

describe("openTrialEventStream", () => {
  class FakeEventSource {
    static CLOSED = 2;
    static instances: FakeEventSource[] = [];
    readyState = 1;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: (() => void) | null = null;
    url: string;
    constructor(url: string) {
      this.url = url;
      FakeEventSource.instances.push(this);
    }
    close() {
      this.readyState = FakeEventSource.CLOSED;
    }
  }

  it("parses incoming messages and forwards them to the callback", () => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    const received: unknown[] = [];
    openTrialEventStream("abc", (event) => received.push(event));

    const source = FakeEventSource.instances[0];
    source.onmessage?.({ data: JSON.stringify({ type: "run_started" }) });

    expect(received).toEqual([{ type: "run_started" }]);
    expect(source.url).toBe("/api/trials/abc/events");
  });

  it("closes the connection and calls onClose after final_verdict_reached", () => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    let closed = false;
    openTrialEventStream("abc", () => {}, () => { closed = true; });

    const source = FakeEventSource.instances[0];
    source.onmessage?.({ data: JSON.stringify({ type: "final_verdict_reached" }) });

    expect(source.readyState).toBe(FakeEventSource.CLOSED);
    expect(closed).toBe(true);
  });

  it("returns a function that closes the connection early", () => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    const close = openTrialEventStream("abc", () => {});
    close();

    expect(FakeEventSource.instances[0].readyState).toBe(FakeEventSource.CLOSED);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./client"`

- [ ] **Step 3: Write `client.ts`**

Create `examples/web/frontend/src/api/client.ts`:

```typescript
import type {
  CatalogResponse,
  PSALMEvent,
  TrialConfigInput,
  TrialDetail,
  TrialSummary,
} from "./types";

export class TrialConflictError extends Error {
  constructor() {
    super("A trial is already in progress.");
    this.name = "TrialConflictError";
  }
}

export class TrialConfigError extends Error {
  code: string;
  context: Record<string, unknown>;

  constructor(code: string, message: string, context: Record<string, unknown>) {
    super(message);
    this.name = "TrialConfigError";
    this.code = code;
    this.context = context;
  }
}

export async function getCatalog(): Promise<CatalogResponse> {
  const response = await fetch("/api/catalog");
  if (!response.ok) {
    throw new Error(`Failed to load catalog: ${response.status}`);
  }
  return response.json();
}

export async function startTrial(config: TrialConfigInput): Promise<{ trial_id: string }> {
  const response = await fetch("/api/trials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (response.status === 409) {
    throw new TrialConflictError();
  }
  if (response.status === 400) {
    const body = await response.json();
    const detail = body.detail as { code: string; message: string; context: Record<string, unknown> };
    throw new TrialConfigError(detail.code, detail.message, detail.context);
  }
  if (!response.ok) {
    throw new Error(`Failed to start trial: ${response.status}`);
  }
  return response.json();
}

export async function getTrial(id: string): Promise<TrialDetail> {
  const response = await fetch(`/api/trials/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to load trial ${id}: ${response.status}`);
  }
  return response.json();
}

export async function listTrials(): Promise<TrialSummary[]> {
  const response = await fetch("/api/trials");
  if (!response.ok) {
    throw new Error(`Failed to load trial history: ${response.status}`);
  }
  return response.json();
}

export function openTrialEventStream(
  id: string,
  onEvent: (event: PSALMEvent) => void,
  onClose?: () => void,
): () => void {
  const source = new EventSource(`/api/trials/${id}/events`);

  source.onmessage = (message) => {
    const event = JSON.parse(message.data) as PSALMEvent;
    onEvent(event);
    if (event.type === "final_verdict_reached" || event.type === "run_failed") {
      source.close();
      onClose?.();
    }
  };

  source.onerror = () => {
    // EventSource auto-retries transient network errors; only treat this as
    // terminal once the connection has actually closed.
    if (source.readyState === EventSource.CLOSED) {
      onClose?.();
    }
  };

  return () => source.close();
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `12 passed` (3 from Tasks 8-9 plus 9 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/api/client.ts examples/web/frontend/src/api/client.test.ts
git commit -m "feat: add typed API client with SSE streaming helper"
```

---

### Task 11: `state/eventReducer.ts` — the shared `applyEvent` function

**Files:**
- Create: `examples/web/frontend/src/state/eventReducer.ts`
- Create: `examples/web/frontend/src/state/eventReducer.test.ts`

**Interfaces:**
- Consumes: `PSALMEvent`, `PSALMResult`, `DimensionScore` from `../api/types` (Task 9).
- Produces: `TranscriptEntry`, `DimensionState`, `TrialState` (types), `createInitialState(): TrialState`, `applyEvent(state: TrialState, event: PSALMEvent): TrialState` — the single function both the live SSE consumer (Task 12) and the replay controller (Task 12) call for every event. **This is the most important piece of the frontend** — both live rendering and replay depend entirely on it being correct, and every one of the three views (Tasks 13-15) reads only from `TrialState`, never from raw events directly.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/state/eventReducer.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type {
  ArgumentSubmitted,
  DimensionStarted,
  DimensionVerdictReached,
  FinalVerdictReached,
  JurorVoteCast,
  RunFailed,
  RunStarted,
} from "../api/types";
import { applyEvent, createInitialState } from "./eventReducer";

function envelope(overrides: Partial<{
  event_id: string; sequence: number; timestamp: string; run_id: string; dimension: string | null;
}> = {}) {
  return {
    event_id: "e1", sequence: 1, timestamp: "2026-01-01T00:00:00Z", run_id: "r1", dimension: null,
    ...overrides,
  };
}

describe("applyEvent", () => {
  it("run_started marks the trial running and records the run id", () => {
    const event: RunStarted = {
      ...envelope(), category: "lifecycle", type: "run_started",
      dimensions: ["Character"], evaluation_strategy: "fully_separate", source_length: 5, target_length: 6,
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.status).toBe("running");
    expect(state.runId).toBe("r1");
    expect(state.evaluationStrategy).toBe("fully_separate");
  });

  it("run_failed marks the trial in an error state with the message", () => {
    const event: RunFailed = {
      ...envelope(), category: "lifecycle", type: "run_failed",
      code: "PSALM-A003", message: "LLM retry limit reached.", context: {},
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.status).toBe("error");
    expect(state.errorMessage).toBe("LLM retry limit reached.");
  });

  it("dimension_started creates a new dimension entry", () => {
    const event: DimensionStarted = {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.dimensionOrder).toEqual(["Character"]);
    expect(state.dimensions["Character"].dimensionType).toBe("infringement");
    expect(state.dimensions["Character"].status).toBe("running");
  });

  it("dimension_started with a null dimension is ignored rather than crashing", () => {
    const event: DimensionStarted = {
      ...envelope({ dimension: null }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.dimensionOrder).toEqual([]);
  });

  it("argument_submitted appends a transcript entry to the right dimension and tracks the speaker", () => {
    let state = applyEvent(createInitialState(), {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    } as DimensionStarted);
    const event: ArgumentSubmitted = {
      ...envelope({ dimension: "Character", event_id: "e2" }), category: "argumentation", type: "argument_submitted",
      round: 1, role: "prosecution", kind: "argument",
      argument: { claim: "The scar matches.", dimension: "Character", proofs: [], agent_role: "prosecutor", round: 1 },
    };
    state = applyEvent(state, event);
    expect(state.dimensions["Character"].transcript).toHaveLength(1);
    expect(state.dimensions["Character"].transcript[0].text).toContain("The scar matches.");
    expect(state.dimensions["Character"].speakingRole).toBe("prosecution");
  });

  it("argument_submitted with a null dimension goes to the shared transcript", () => {
    const event: ArgumentSubmitted = {
      ...envelope({ dimension: null }), category: "argumentation", type: "argument_submitted",
      round: 1, role: "prosecution", kind: "argument",
      argument: { claim: "Shared claim.", dimension: "Character", proofs: [], agent_role: "prosecutor", round: 1 },
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.sharedTranscript).toHaveLength(1);
    expect(state.dimensions).toEqual({});
  });

  it("juror_vote_cast records the vote under the right dimension", () => {
    let state = applyEvent(createInitialState(), {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    } as DimensionStarted);
    const event: JurorVoteCast = {
      ...envelope({ dimension: "Character" }), category: "deliberation", type: "juror_vote_cast",
      round: 1, juror_id: "juror-0", vote: "Guilty", rationale: "Strong evidence.", dimension_scores: [],
    };
    state = applyEvent(state, event);
    expect(state.dimensions["Character"].jurorVotes["juror-0"]).toEqual({
      vote: "Guilty", rationale: "Strong evidence.", dimensionScores: [],
    });
  });

  it("dimension_verdict_reached marks that dimension done with its verdict", () => {
    let state = applyEvent(createInitialState(), {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    } as DimensionStarted);
    const event: DimensionVerdictReached = {
      ...envelope({ dimension: "Character" }), category: "verdict", type: "dimension_verdict_reached",
      dimension_type: "infringement", importance: "high", verdict: "Guilty", weighted_score: 0.8,
    };
    state = applyEvent(state, event);
    expect(state.dimensions["Character"].status).toBe("done");
    expect(state.dimensions["Character"].verdict).toBe("Guilty");
    expect(state.dimensions["Character"].weightedScore).toBe(0.8);
  });

  it("final_verdict_reached marks the whole trial done and stores the result", () => {
    const event: FinalVerdictReached = {
      ...envelope(), category: "verdict", type: "final_verdict_reached",
      result: {
        verdict: "Guilty", rationale: "Because.", dimension_verdicts: [],
        metadata: {
          duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
          voting_strategy_applied: "unanimous", agent_failures: [],
        },
      },
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.status).toBe("done");
    expect(state.finalResult?.verdict).toBe("Guilty");
  });

  it("is a pure function — never mutates the input state", () => {
    const initial = createInitialState();
    const frozen = JSON.stringify(initial);
    applyEvent(initial, {
      ...envelope(), category: "lifecycle", type: "run_started",
      dimensions: ["Character"], evaluation_strategy: "fully_separate", source_length: 1, target_length: 1,
    } as RunStarted);
    expect(JSON.stringify(initial)).toBe(frozen);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./eventReducer"`

- [ ] **Step 3: Write `eventReducer.ts`**

Create `examples/web/frontend/src/state/eventReducer.ts`:

```typescript
import type { DimensionScore, PSALMEvent, PSALMResult } from "../api/types";

export interface TranscriptEntry {
  id: string;
  timestamp: string;
  dimension: string | null;
  kind: string;
  role?: string;
  text: string;
  raw: PSALMEvent;
}

export interface DimensionState {
  name: string;
  dimensionType: string | null;
  importance: string | null;
  phase: "argumentation" | "deliberation" | "verdict";
  currentRound: number;
  status: "running" | "done";
  verdict: string | null;
  weightedScore: number | null;
  speakingRole: string | null;
  latestSpeech: string | null;
  jurorVotes: Record<string, { vote: string; rationale: string; dimensionScores: DimensionScore[] }>;
  rejectedArgumentCount: number;
  transcript: TranscriptEntry[];
}

export interface TrialState {
  runId: string | null;
  status: "idle" | "running" | "done" | "error";
  evaluationStrategy: string | null;
  dimensionOrder: string[];
  dimensions: Record<string, DimensionState>;
  sharedTranscript: TranscriptEntry[];
  finalResult: PSALMResult | null;
  errorMessage: string | null;
}

export function createInitialState(): TrialState {
  return {
    runId: null,
    status: "idle",
    evaluationStrategy: null,
    dimensionOrder: [],
    dimensions: {},
    sharedTranscript: [],
    finalResult: null,
    errorMessage: null,
  };
}

function ensureDimension(state: TrialState, name: string): TrialState {
  if (state.dimensions[name]) return state;
  const dimensionState: DimensionState = {
    name, dimensionType: null, importance: null, phase: "argumentation", currentRound: 0,
    status: "running", verdict: null, weightedScore: null, speakingRole: null, latestSpeech: null,
    jurorVotes: {}, rejectedArgumentCount: 0, transcript: [],
  };
  return {
    ...state,
    dimensionOrder: [...state.dimensionOrder, name],
    dimensions: { ...state.dimensions, [name]: dimensionState },
  };
}

function appendEntry(dim: DimensionState, entry: TranscriptEntry): DimensionState {
  return { ...dim, transcript: [...dim.transcript, entry] };
}

function updateDimension(
  state: TrialState, name: string, updater: (dim: DimensionState) => DimensionState,
): TrialState {
  const current = state.dimensions[name];
  if (!current) return state;
  return { ...state, dimensions: { ...state.dimensions, [name]: updater(current) } };
}

function appendShared(state: TrialState, entry: TranscriptEntry): TrialState {
  return { ...state, sharedTranscript: [...state.sharedTranscript, entry] };
}

export function applyEvent(state: TrialState, event: PSALMEvent): TrialState {
  switch (event.type) {
    case "run_started":
      return {
        ...state, runId: event.run_id, status: "running", evaluationStrategy: event.evaluation_strategy,
      };

    case "run_failed":
      return { ...state, status: "error", errorMessage: event.message };

    case "dimension_started": {
      if (event.dimension === null) return state;
      const withDim = ensureDimension(state, event.dimension);
      return updateDimension(withDim, event.dimension, (dim) => ({
        ...dim, dimensionType: event.dimension_type, importance: event.importance,
      }));
    }

    case "argumentation_round_started": {
      if (event.dimension === null) return state;
      return updateDimension(state, event.dimension, (dim) => ({
        ...dim, phase: "argumentation", currentRound: event.round,
      }));
    }

    case "argument_submitted": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "argument", role: event.role,
        text: `${event.role === "prosecution" ? "Prosecutor" : "Defense"} `
          + `${event.kind === "counter" ? "counters" : "argues"}: "${event.argument.claim}"`,
        raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, speakingRole: event.role, latestSpeech: event.argument.claim }, entry,
      ));
    }

    case "argument_validated": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "validation", role: event.role, text: `Judge accepts the ${event.role} argument.`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "argument_rejected": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "rejection", role: event.role, text: `Judge sustains an objection: "${event.reason}"`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, rejectedArgumentCount: dim.rejectedArgumentCount + 1 }, entry,
      ));
    }

    case "closing_statement_delivered": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "closing_statement", role: event.role, text: `${event.role}: "${event.statement}"`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "argumentation_stability_checked": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "stability_check",
        text: event.stability_detected ? "The argumentation has stabilized." : "Argumentation continues.",
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "closing_argument_delivered": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "closing_argument", role: event.role,
        text: `${event.role} closing argument: "${event.statement}"`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "argument_batch_completeness_retry": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "completeness_retry", role: event.role,
        text: `The Judge asks the ${event.role} to clarify (attempt ${event.attempt}/${event.max_attempts}).`,
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "deliberation_round_started": {
      if (event.dimension === null) return state;
      return updateDimension(state, event.dimension, (dim) => ({
        ...dim, phase: "deliberation", currentRound: event.round,
      }));
    }

    case "juror_vote_cast": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "vote", role: event.juror_id, text: `${event.juror_id} votes ${event.vote}.`, raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry({
        ...dim,
        jurorVotes: {
          ...dim.jurorVotes,
          [event.juror_id]: {
            vote: event.vote, rationale: event.rationale, dimensionScores: event.dimension_scores,
          },
        },
      }, entry));
    }

    case "jury_consensus_checked": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "consensus",
        text: event.is_unanimous
          ? `The jury unanimously finds ${event.top_verdict}.`
          : "The jury has not reached consensus.",
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "jury_discussion_message": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "discussion", role: event.juror_id, text: `${event.juror_id}: "${event.message}"`, raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, speakingRole: event.juror_id, latestSpeech: event.message }, entry,
      ));
    }

    case "voting_strategy_applied": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "voting_strategy",
        text: event.is_tie
          ? `${event.strategy_name} could not break the tie.`
          : `${event.strategy_name} resolves the vote: ${event.verdict}.`,
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "dimension_verdict_reached": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "dimension_verdict",
        text: `Verdict for ${event.dimension}: ${event.verdict} (score ${event.weighted_score.toFixed(2)}).`,
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, phase: "verdict", status: "done", verdict: event.verdict, weightedScore: event.weighted_score },
        entry,
      ));
    }

    case "final_verdict_reached":
      return { ...state, status: "done", finalResult: event.result };

    case "agent_call_retrying": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "agent_retry", role: event.role,
        text: `${event.role} had a transient error, retrying (attempt ${event.attempt}/${event.max_attempts})...`,
        raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "agent_call_failed": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "agent_failure", role: event.role,
        text: `${event.role} failed after ${event.attempts} attempts: ${event.error}`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    default: {
      const _exhaustive: never = event;
      return state;
    }
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `22 passed` (12 from Tasks 8-10 plus 10 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors — pay particular attention to the `default: { const _exhaustive: never = event; ... }` case, which only compiles if every member of the `PSALMEvent` union has a preceding `case` — this is TypeScript's exhaustiveness check catching any event type this reducer forgot to handle.

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/state/eventReducer.ts examples/web/frontend/src/state/eventReducer.test.ts
git commit -m "feat: add the shared applyEvent reducer for live and replay state"
```

---

### Task 12: `state/store.ts` — Zustand store wiring live SSE and the replay controller

**Files:**
- Create: `examples/web/frontend/src/state/store.ts`
- Create: `examples/web/frontend/src/state/store.test.ts`

**Interfaces:**
- Consumes: `openTrialEventStream` (Task 10), `applyEvent`/`createInitialState`/`TrialState` (Task 11).
- Produces: `useTrialStore` (a Zustand hook) with `mode: "idle" | "live" | "replay"`, `state: TrialState`, `allEvents: PSALMEvent[]`, `isPlaying: boolean`, `replaySpeed: number`, `replayIndex: number`, and actions `startLive(trialId)`, `stopLive()`, `reset()`, `loadForReplay(events)`, `play()`, `pause()`, `scrubTo(index)`, `setReplaySpeed(speed)`. Later tasks (13-20) read `state`/`mode`/`allEvents`/`isPlaying`/`replayIndex` and call these actions — no other module talks to `applyEvent` or `openTrialEventStream` directly.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/state/store.test.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { FinalVerdictReached, PSALMEvent, RunStarted } from "../api/types";
import { useTrialStore } from "./store";

function makeRunStarted(overrides: Partial<RunStarted> = {}): RunStarted {
  return {
    event_id: "e1", sequence: 1, timestamp: "t", run_id: "r1", dimension: null,
    category: "lifecycle", type: "run_started",
    dimensions: ["Character"], evaluation_strategy: "fully_separate", source_length: 1, target_length: 1,
    ...overrides,
  };
}

function makeFinalVerdict(overrides: Partial<FinalVerdictReached> = {}): FinalVerdictReached {
  return {
    event_id: "e2", sequence: 2, timestamp: "t", run_id: "r1", dimension: null,
    category: "verdict", type: "final_verdict_reached",
    result: {
      verdict: "Guilty", rationale: "Because.", dimension_verdicts: [],
      metadata: {
        duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
        voting_strategy_applied: "unanimous", agent_failures: [],
      },
    },
    ...overrides,
  };
}

describe("useTrialStore", () => {
  beforeEach(() => {
    useTrialStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("startLive opens an event stream and applies incoming events", () => {
    let capturedOnEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, onEvent) => {
      capturedOnEvent = onEvent;
      return () => {};
    });

    useTrialStore.getState().startLive("trial-1");
    expect(useTrialStore.getState().mode).toBe("live");

    capturedOnEvent?.(makeRunStarted());
    expect(useTrialStore.getState().state.status).toBe("running");
    expect(useTrialStore.getState().allEvents).toHaveLength(1);
  });

  it("stopLive closes the underlying stream", () => {
    const close = vi.fn();
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(close);

    useTrialStore.getState().startLive("trial-1");
    useTrialStore.getState().stopLive();
    expect(close).toHaveBeenCalled();
  });

  it("loadForReplay resets state and stores the full event list", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    const s = useTrialStore.getState();
    expect(s.mode).toBe("replay");
    expect(s.allEvents).toHaveLength(2);
    expect(s.state.status).toBe("idle");
  });

  it("scrubTo recomputes state deterministically from the beginning", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    useTrialStore.getState().scrubTo(0);
    expect(useTrialStore.getState().state.status).toBe("running");
    expect(useTrialStore.getState().state.finalResult).toBeNull();

    useTrialStore.getState().scrubTo(1);
    expect(useTrialStore.getState().state.finalResult?.verdict).toBe("Guilty");
  });

  it("scrubTo clamps to the valid event range", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted()]);
    useTrialStore.getState().scrubTo(99);
    expect(useTrialStore.getState().replayIndex).toBe(0);
  });

  it("play advances through events over time and stops at the end", () => {
    vi.useFakeTimers();
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    useTrialStore.getState().setReplaySpeed(1);
    useTrialStore.getState().play();
    expect(useTrialStore.getState().isPlaying).toBe(true);

    vi.advanceTimersByTime(2000);

    expect(useTrialStore.getState().isPlaying).toBe(false);
    expect(useTrialStore.getState().state.finalResult?.verdict).toBe("Guilty");
  });

  it("pause stops advancing", () => {
    vi.useFakeTimers();
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    useTrialStore.getState().play();
    useTrialStore.getState().pause();
    const indexAfterPause = useTrialStore.getState().replayIndex;

    vi.advanceTimersByTime(2000);

    expect(useTrialStore.getState().replayIndex).toBe(indexAfterPause);
    expect(useTrialStore.getState().isPlaying).toBe(false);
  });

  it("reset clears everything back to idle", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted()]);
    useTrialStore.getState().scrubTo(0);
    useTrialStore.getState().reset();
    const s = useTrialStore.getState();
    expect(s.mode).toBe("idle");
    expect(s.allEvents).toEqual([]);
    expect(s.state.status).toBe("idle");
  });
});
```

- [ ] **Step 2: Install Zustand and run tests to verify they fail**

Run: `cd examples/web/frontend && npm install zustand@^4.5.4` (if not already installed from Task 8's `package.json`, this is a no-op)

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./store"`

- [ ] **Step 3: Write `store.ts`**

Create `examples/web/frontend/src/state/store.ts`:

```typescript
import { create } from "zustand";
import { openTrialEventStream } from "../api/client";
import type { PSALMEvent } from "../api/types";
import { applyEvent, createInitialState } from "./eventReducer";
import type { TrialState } from "./eventReducer";

export type PlaybackMode = "idle" | "live" | "replay";

interface TrialStoreState {
  mode: PlaybackMode;
  state: TrialState;
  allEvents: PSALMEvent[];
  isPlaying: boolean;
  replaySpeed: number;
  replayIndex: number;

  startLive: (trialId: string) => void;
  stopLive: () => void;
  reset: () => void;
  loadForReplay: (events: PSALMEvent[]) => void;
  play: () => void;
  pause: () => void;
  scrubTo: (index: number) => void;
  setReplaySpeed: (speed: number) => void;
}

let closeLiveStream: (() => void) | null = null;
let replayTimer: ReturnType<typeof setInterval> | null = null;

function stopReplayTimer(): void {
  if (replayTimer !== null) {
    clearInterval(replayTimer);
    replayTimer = null;
  }
}

function reduceUpTo(events: PSALMEvent[], index: number): TrialState {
  let state = createInitialState();
  for (let i = 0; i <= index && i < events.length; i++) {
    state = applyEvent(state, events[i]);
  }
  return state;
}

export const useTrialStore = create<TrialStoreState>((set, get) => ({
  mode: "idle",
  state: createInitialState(),
  allEvents: [],
  isPlaying: false,
  replaySpeed: 1,
  replayIndex: -1,

  startLive: (trialId: string) => {
    closeLiveStream?.();
    stopReplayTimer();
    set({ mode: "live", state: createInitialState(), allEvents: [], isPlaying: false, replayIndex: -1 });
    closeLiveStream = openTrialEventStream(
      trialId,
      (event) => {
        set((s) => ({ state: applyEvent(s.state, event), allEvents: [...s.allEvents, event] }));
      },
      () => {
        closeLiveStream = null;
      },
    );
  },

  stopLive: () => {
    closeLiveStream?.();
    closeLiveStream = null;
  },

  reset: () => {
    closeLiveStream?.();
    closeLiveStream = null;
    stopReplayTimer();
    set({ mode: "idle", state: createInitialState(), allEvents: [], isPlaying: false, replayIndex: -1 });
  },

  loadForReplay: (events: PSALMEvent[]) => {
    stopReplayTimer();
    set({ mode: "replay", allEvents: events, replayIndex: -1, state: createInitialState(), isPlaying: false });
  },

  play: () => {
    stopReplayTimer();
    set({ isPlaying: true });
    const tick = () => {
      const { allEvents, replayIndex } = get();
      const nextIndex = replayIndex + 1;
      if (nextIndex >= allEvents.length) {
        stopReplayTimer();
        set({ isPlaying: false });
        return;
      }
      set({ replayIndex: nextIndex, state: reduceUpTo(allEvents, nextIndex) });
    };
    const { replaySpeed } = get();
    replayTimer = setInterval(tick, Math.max(20, 400 / replaySpeed));
  },

  pause: () => {
    stopReplayTimer();
    set({ isPlaying: false });
  },

  scrubTo: (index: number) => {
    stopReplayTimer();
    set((s) => {
      const clamped = Math.max(-1, Math.min(index, s.allEvents.length - 1));
      return { replayIndex: clamped, state: reduceUpTo(s.allEvents, clamped), isPlaying: false };
    });
  },

  setReplaySpeed: (speed: number) => {
    set({ replaySpeed: speed });
    if (get().isPlaying) {
      get().play();
    }
  },
}));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `30 passed` (22 from Tasks 8-11 plus 8 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/state/store.ts examples/web/frontend/src/state/store.test.ts examples/web/frontend/package.json examples/web/frontend/package-lock.json
git commit -m "feat: add Zustand store wiring live SSE and replay controller"
```

---

### Task 13: `mergeTranscript` helper, test fixtures, and `TranscriptView`

**Files:**
- Modify: `examples/web/frontend/src/state/eventReducer.ts`
- Create: `examples/web/frontend/src/state/testFixtures.ts`
- Create: `examples/web/frontend/src/views/TranscriptView.tsx`
- Create: `examples/web/frontend/src/views/TranscriptView.test.tsx`

**Interfaces:**
- Consumes: `TrialState`/`DimensionState`/`TranscriptEntry` (Task 11).
- Produces:
  - `eventReducer.ts` addition: `mergeTranscript(sharedTranscript: TranscriptEntry[], dimension: DimensionState | null): TranscriptEntry[]` — combines and chronologically sorts (by `raw.sequence`) the shared-strategy transcript with a specific dimension's own transcript. Used by all three views (Tasks 13-15).
  - `testFixtures.ts`: `makeDimensionState(overrides?: Partial<DimensionState>): DimensionState` — a reusable factory for view tests, avoiding each view's test file re-declaring the same boilerplate object.
  - `TranscriptView.tsx`: `export default function TranscriptView({ dimension, sharedTranscript }: { dimension: DimensionState | null; sharedTranscript: TranscriptEntry[] }): JSX.Element`.

- [ ] **Step 1: Add `mergeTranscript` to `eventReducer.ts`**

Append to the end of `examples/web/frontend/src/state/eventReducer.ts`:

```typescript
export function mergeTranscript(
  sharedTranscript: TranscriptEntry[], dimension: DimensionState | null,
): TranscriptEntry[] {
  const combined = [...sharedTranscript, ...(dimension?.transcript ?? [])];
  return combined.sort((a, b) => a.raw.sequence - b.raw.sequence);
}
```

- [ ] **Step 2: Write the test fixture factory**

Create `examples/web/frontend/src/state/testFixtures.ts`:

```typescript
import type { DimensionState } from "./eventReducer";

export function makeDimensionState(overrides: Partial<DimensionState> = {}): DimensionState {
  return {
    name: "Character",
    dimensionType: "infringement",
    importance: "high",
    phase: "argumentation",
    currentRound: 1,
    status: "running",
    verdict: null,
    weightedScore: null,
    speakingRole: null,
    latestSpeech: null,
    jurorVotes: {},
    rejectedArgumentCount: 0,
    transcript: [],
    ...overrides,
  };
}
```

- [ ] **Step 3: Write the failing tests for `TranscriptView`**

Create `examples/web/frontend/src/views/TranscriptView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TranscriptView from "./TranscriptView";

function withSequence(sequence: number): PSALMEvent {
  return { sequence } as PSALMEvent;
}

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
});
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./TranscriptView"`

- [ ] **Step 5: Write `TranscriptView.tsx`**

Create `examples/web/frontend/src/views/TranscriptView.tsx`:

```tsx
import { useMemo } from "react";
import type { DimensionState, TranscriptEntry } from "../state/eventReducer";
import { mergeTranscript } from "../state/eventReducer";

interface TranscriptViewProps {
  dimension: DimensionState | null;
  sharedTranscript: TranscriptEntry[];
}

const ROLE_COLORS: Record<string, string> = {
  prosecution: "#b45309",
  defense: "#1d4ed8",
};

function entryColor(entry: TranscriptEntry): string {
  if (["rejection", "validation", "consensus", "stability_check"].includes(entry.kind)) {
    return "#6b21a8";
  }
  if (entry.role && ROLE_COLORS[entry.role]) return ROLE_COLORS[entry.role];
  return "#4b5563";
}

export default function TranscriptView({ dimension, sharedTranscript }: TranscriptViewProps) {
  const entries = useMemo(
    () => mergeTranscript(sharedTranscript, dimension),
    [sharedTranscript, dimension],
  );

  if (entries.length === 0) {
    return <p className="transcript-empty">Waiting for the trial to begin...</p>;
  }

  return (
    <div className="transcript-view" aria-live="polite">
      {entries.map((entry) => (
        <div
          key={entry.id}
          data-testid="transcript-entry"
          className="transcript-entry"
          style={{ borderLeftColor: entryColor(entry) }}
        >
          {entry.text}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `33 passed` (30 from Tasks 8-12 plus 3 new)

- [ ] **Step 7: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 8: Commit**

```bash
git add examples/web/frontend/src/state/eventReducer.ts examples/web/frontend/src/state/testFixtures.ts examples/web/frontend/src/views/
git commit -m "feat: add mergeTranscript helper and TranscriptView"
```

---

### Task 14: `StageView`

**Files:**
- Create: `examples/web/frontend/src/views/StageView.tsx`
- Create: `examples/web/frontend/src/views/StageView.test.tsx`

**Interfaces:**
- Consumes: `DimensionState` (Task 11), `makeDimensionState` (Task 13).
- Produces: `StageView.tsx`: `export default function StageView({ dimension }: { dimension: DimensionState | null }): JSX.Element` — the default live-trial view (courtroom floor plan with a speech bubble over whoever's currently acting).

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/views/StageView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import StageView from "./StageView";

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
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./StageView"`

- [ ] **Step 3: Write `StageView.tsx`**

Create `examples/web/frontend/src/views/StageView.tsx`:

```tsx
import type { DimensionState } from "../state/eventReducer";

interface StageViewProps {
  dimension: DimensionState | null;
}

function phaseLabel(dimension: DimensionState): string {
  if (dimension.phase === "verdict") return `Verdict: ${dimension.verdict}`;
  if (dimension.phase === "deliberation") return `Deliberation — round ${dimension.currentRound}`;
  return `Argumentation — round ${dimension.currentRound}`;
}

export default function StageView({ dimension }: StageViewProps) {
  if (dimension === null) {
    return <p className="stage-empty">Waiting for the trial to begin...</p>;
  }

  const voteCounts = Object.values(dimension.jurorVotes).reduce<Record<string, number>>((acc, v) => {
    acc[v.vote] = (acc[v.vote] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="stage-view">
      <div className="stage-phase-indicator">{phaseLabel(dimension)}</div>

      <div className="stage-bench" data-testid="stage-bench">
        <span className="stage-role-label">Judge</span>
        {dimension.rejectedArgumentCount > 0 && (
          <p className="stage-speech">{dimension.rejectedArgumentCount} objection(s) sustained so far.</p>
        )}
      </div>

      <div className="stage-parties">
        <div
          data-testid="stage-podium-prosecution"
          className={`stage-podium ${dimension.speakingRole === "prosecution" ? "stage-speaking" : ""}`}
        >
          <span className="stage-role-label">Prosecutor</span>
          {dimension.speakingRole === "prosecution" && dimension.latestSpeech && (
            <p className="stage-speech">&quot;{dimension.latestSpeech}&quot;</p>
          )}
        </div>
        <div
          data-testid="stage-podium-defense"
          className={`stage-podium ${dimension.speakingRole === "defense" ? "stage-speaking" : ""}`}
        >
          <span className="stage-role-label">Defense</span>
          {dimension.speakingRole === "defense" && dimension.latestSpeech && (
            <p className="stage-speech">&quot;{dimension.latestSpeech}&quot;</p>
          )}
        </div>
      </div>

      <div className="stage-jury" data-testid="stage-jury">
        <span className="stage-role-label">Jury ({Object.keys(dimension.jurorVotes).length} voted)</span>
        <div className="stage-jury-tally">
          {Object.entries(voteCounts).map(([vote, count]) => (
            <span key={vote} className="stage-jury-vote">{count} × {vote}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `39 passed` (33 from Tasks 8-13 plus 6 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/views/StageView.tsx examples/web/frontend/src/views/StageView.test.tsx
git commit -m "feat: add StageView (default courtroom floor-plan live view)"
```

---

### Task 15: `TimelineView`

**Files:**
- Create: `examples/web/frontend/src/views/TimelineView.tsx`
- Create: `examples/web/frontend/src/views/TimelineView.test.tsx`

**Interfaces:**
- Consumes: `DimensionState`/`TranscriptEntry`/`mergeTranscript` (Tasks 11, 13), `makeDimensionState` (Task 13).
- Produces: `TimelineView.tsx`: `export default function TimelineView({ dimension, sharedTranscript }: { dimension: DimensionState | null; sharedTranscript: TranscriptEntry[] }): JSX.Element`.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/views/TimelineView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TimelineView from "./TimelineView";

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
    expect(screen.getByText(/▶ Argumentation round 2/)).toBeInTheDocument();
    expect(screen.getByText(/✅ Argumentation round 1/)).toBeInTheDocument();
  });

  it("marks verdict as done once reached", () => {
    render(<TimelineView dimension={makeDimensionState({ phase: "verdict", currentRound: 2 })} sharedTranscript={[]} />);
    expect(screen.getByText(/✅ Verdict/)).toBeInTheDocument();
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

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./TimelineView"`

- [ ] **Step 3: Write `TimelineView.tsx`**

Create `examples/web/frontend/src/views/TimelineView.tsx`:

```tsx
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

function statusIcon(status: StepInfo["status"]): string {
  if (status === "done") return "✅";
  if (status === "current") return "▶";
  return "○";
}

export default function TimelineView({ dimension, sharedTranscript }: TimelineViewProps) {
  if (dimension === null) {
    return <p className="timeline-empty">Waiting for the trial to begin...</p>;
  }

  const steps = buildSteps(dimension);
  const entries = mergeTranscript(sharedTranscript, dimension);

  return (
    <div className="timeline-view">
      <div className="timeline-steps">
        {steps.map((step) => (
          <div key={step.label} className={`timeline-step timeline-step-${step.status}`}>
            {statusIcon(step.status)} {step.label}
          </div>
        ))}
      </div>
      <div className="timeline-transcript">
        {entries.map((entry) => (
          <div key={entry.id} className="timeline-entry">{entry.text}</div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `43 passed` (39 from Tasks 8-14 plus 4 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/views/TimelineView.tsx examples/web/frontend/src/views/TimelineView.test.tsx
git commit -m "feat: add TimelineView"
```

---

### Task 16: `AgentConfigPanel` and `SetupPage` — the full configuration form

**Files:**
- Create: `examples/web/frontend/src/components/AgentConfigPanel.tsx`
- Create: `examples/web/frontend/src/components/AgentConfigPanel.test.tsx`
- Create: `examples/web/frontend/src/routes/SetupPage.tsx`
- Create: `examples/web/frontend/src/routes/SetupPage.test.tsx`
- Modify: `examples/web/frontend/package.json`

**Interfaces:**
- Consumes: `getCatalog`/`startTrial`/`TrialConflictError`/`TrialConfigError` (Task 10), `AgentConfigInput`/`JurorConfigInput`/`CatalogResponse`/`ProviderPreset` (Task 9).
- Produces: `AgentConfigPanel.tsx`: `export default function AgentConfigPanel({ label, config, onChange, envAvailable, providerPresets }: { label: string; config: AgentConfigInput; onChange: (config: AgentConfigInput) => void; envAvailable: boolean; providerPresets: ProviderPreset[] }): JSX.Element` — reused once for Prosecutor, Defense, Judge, and once per juror. `SetupPage.tsx`: `export default function SetupPage(): JSX.Element` — loads the catalog, renders the full form (text/presets, dimensions, advanced settings, agent configs, jury add/remove), calls `startTrial()` on submit, and navigates to `/trial/:id` on success (via `react-router-dom`'s `useNavigate`).

- [ ] **Step 1: Install `react-router-dom`**

Run: `cd examples/web/frontend && npm install react-router-dom@^6.26.0`
Expected: installs with no errors (already listed in Task 8's `package.json`, so this may be a no-op if `npm install` already resolved it — run it anyway to be sure).

- [ ] **Step 2: Write the failing tests for `AgentConfigPanel`**

Create `examples/web/frontend/src/components/AgentConfigPanel.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AgentConfigPanel from "./AgentConfigPanel";

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
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./AgentConfigPanel"`

- [ ] **Step 4: Write `AgentConfigPanel.tsx`**

Create `examples/web/frontend/src/components/AgentConfigPanel.tsx`:

```tsx
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

  return (
    <fieldset className="agent-config-panel">
      <legend>{label}</legend>

      <label htmlFor={`${inputId}-provider`}>Provider</label>
      <select id={`${inputId}-provider`} onChange={(e) => applyProviderPreset(e.target.value)} defaultValue="">
        <option value="" disabled>Choose a provider (optional)</option>
        {providerPresets.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>

      <label htmlFor={`${inputId}-base-url`}>Base URL</label>
      <input
        id={`${inputId}-base-url`}
        type="text"
        value={config.base_url ?? ""}
        onChange={(e) => onChange({ ...config, base_url: e.target.value })}
        placeholder={envAvailable ? "leave blank to use environment variable" : "required"}
      />

      <label htmlFor={`${inputId}-api-key`}>API key</label>
      <input
        id={`${inputId}-api-key`}
        type="password"
        value={config.api_key ?? ""}
        onChange={(e) => onChange({ ...config, api_key: e.target.value })}
        placeholder={requiredOrEnv}
      />

      <label htmlFor={`${inputId}-model`}>Model</label>
      <input
        id={`${inputId}-model`}
        type="text"
        value={config.model ?? ""}
        onChange={(e) => onChange({ ...config, model: e.target.value })}
        placeholder={envAvailable ? "leave blank to use environment variable" : "required"}
      />

      <label htmlFor={`${inputId}-temperature`}>Temperature</label>
      <input
        id={`${inputId}-temperature`}
        type="number"
        step={0.1}
        min={0}
        max={2}
        value={config.temperature ?? ""}
        onChange={(e) => onChange({
          ...config, temperature: e.target.value === "" ? undefined : Number(e.target.value),
        })}
      />
    </fieldset>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `47 passed` (43 from Tasks 8-15 plus 4 new)

- [ ] **Step 6: Write the failing tests for `SetupPage`**

Create `examples/web/frontend/src/routes/SetupPage.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import SetupPage from "./SetupPage";

const fakeCatalog = {
  dimensions: [
    { name: "Character", dimension_type: "infringement", importance: "high", description: "d", sub_dimensions: [] },
    { name: "Scenes a Faire", dimension_type: "exception", importance: "medium", description: "d", sub_dimensions: [] },
  ],
  presets: [{ id: "infringing", label: "Infringing example", source_text: "SRC", target_text: "TGT" }],
  evaluation_strategies: [{ value: "fully_separate", label: "Fully separate", description: "d" }],
  provider_presets: [{ id: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1" }],
  env_status: { PSALM_API_KEY: true },
};

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
  it("loads the catalog and shows Character as a selectable dimension", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    expect(await screen.findByLabelText("Character")).toBeInTheDocument();
  });

  it("applying a preset fills the source and target text fields", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Character");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    expect(screen.getByLabelText("Source text")).toHaveValue("SRC");
    expect(screen.getByLabelText("Target text")).toHaveValue("TGT");
  });

  it("disables Start Trial until source, target, and at least one dimension are set", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByText("Agents");
    expect(screen.getByText("Start Trial")).toBeDisabled();
  });

  it("submits the trial with the right payload and navigates on success", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    const startTrialSpy = vi.spyOn(client, "startTrial").mockResolvedValue({ trial_id: "abc" });
    renderSetupPage();
    await screen.findByLabelText("Character");

    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByLabelText("Character"));
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
    await screen.findByLabelText("Character");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Start Trial"));

    expect(await screen.findByRole("alert")).toHaveTextContent("No API key provided.");
  });

  it("adds and removes jurors, never going below 3", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByText("Jury");
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(3);
    expect(screen.queryByText("Remove juror 0")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Add juror"));
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(4);
    expect(screen.getByText("Remove juror 3")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Remove juror 3"));
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(3);
  });
});
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./SetupPage"`

- [ ] **Step 8: Write `SetupPage.tsx`**

Create `examples/web/frontend/src/routes/SetupPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrialConfigError, TrialConflictError, getCatalog, startTrial } from "../api/client";
import type { AgentConfigInput, CatalogResponse, JurorConfigInput } from "../api/types";
import AgentConfigPanel from "../components/AgentConfigPanel";

function emptyAgentConfig(): AgentConfigInput {
  return {};
}

function emptyJurorConfig(): JurorConfigInput {
  return {};
}

export default function SetupPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [sourceText, setSourceText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [evaluationStrategy, setEvaluationStrategy] = useState("fully_separate");
  const [argumentationRounds, setArgumentationRounds] = useState(3);
  const [deliberationRounds, setDeliberationRounds] = useState(2);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(120);
  const [advancedOpen, setAdvancedOpen] = useState(false);

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
    return <p role="alert">Failed to load configuration options: {catalogError}</p>;
  }
  if (!catalog) {
    return <p>Loading...</p>;
  }

  const canSubmit = (
    sourceText.trim() !== "" && targetText.trim() !== "" && selectedDimensions.length > 0 && !submitting
  );

  return (
    <div className="setup-page">
      <h1>New trial</h1>

      <section>
        <h2>Texts</h2>
        <label htmlFor="preset-select">Preset</label>
        <select id="preset-select" onChange={(e) => applyPreset(e.target.value)} defaultValue="">
          <option value="" disabled>Choose a preset (optional)</option>
          {catalog.presets.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <label htmlFor="source-text">Source text</label>
        <textarea id="source-text" value={sourceText} onChange={(e) => setSourceText(e.target.value)} rows={6} />
        <label htmlFor="target-text">Target text</label>
        <textarea id="target-text" value={targetText} onChange={(e) => setTargetText(e.target.value)} rows={6} />
      </section>

      <section>
        <h2>Dimensions</h2>
        {(["infringement", "exception"] as const).map((type) => (
          <div key={type}>
            <h3>{type === "infringement" ? "Infringement dimensions" : "Exception dimensions"}</h3>
            {catalog.dimensions.filter((d) => d.dimension_type === type).map((d) => (
              <label key={d.name} title={d.description}>
                <input
                  type="checkbox"
                  checked={selectedDimensions.includes(d.name)}
                  onChange={() => toggleDimension(d.name)}
                />
                {d.name}
              </label>
            ))}
          </div>
        ))}
      </section>

      <section>
        <button type="button" onClick={() => setAdvancedOpen((v) => !v)}>
          {advancedOpen ? "Hide" : "Show"} advanced settings
        </button>
        {advancedOpen && (
          <div>
            <label htmlFor="strategy-select">Evaluation strategy</label>
            <select
              id="strategy-select" value={evaluationStrategy}
              onChange={(e) => setEvaluationStrategy(e.target.value)}
            >
              {catalog.evaluation_strategies.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <label htmlFor="argumentation-rounds">Argumentation rounds</label>
            <input
              id="argumentation-rounds" type="number" min={1} value={argumentationRounds}
              onChange={(e) => setArgumentationRounds(Number(e.target.value))}
            />
            <label htmlFor="deliberation-rounds">Deliberation rounds</label>
            <input
              id="deliberation-rounds" type="number" min={1} value={deliberationRounds}
              onChange={(e) => setDeliberationRounds(Number(e.target.value))}
            />
            <label htmlFor="time-limit">Time limit (seconds)</label>
            <input
              id="time-limit" type="number" min={1} value={timeLimitSeconds}
              onChange={(e) => setTimeLimitSeconds(Number(e.target.value))}
            />
          </div>
        )}
      </section>

      <section>
        <h2>Agents</h2>
        <AgentConfigPanel
          label="Prosecutor" config={prosecutor} onChange={setProsecutor}
          envAvailable={catalog.env_status.PSALM_PROSECUTOR_API_KEY ?? catalog.env_status.PSALM_API_KEY}
          providerPresets={catalog.provider_presets}
        />
        <AgentConfigPanel
          label="Defense" config={defense} onChange={setDefense}
          envAvailable={catalog.env_status.PSALM_DEFENSE_API_KEY ?? catalog.env_status.PSALM_API_KEY}
          providerPresets={catalog.provider_presets}
        />
        <AgentConfigPanel
          label="Judge" config={judge} onChange={setJudge}
          envAvailable={catalog.env_status.PSALM_JUDGE_API_KEY ?? catalog.env_status.PSALM_API_KEY}
          providerPresets={catalog.provider_presets}
        />

        <h3>Jury</h3>
        {jury.map((jurorConfig, index) => (
          <div key={index}>
            <AgentConfigPanel
              label={`Juror ${index}`} config={jurorConfig}
              onChange={(updated) => setJury((current) => (
                current.map((j, i) => (i === index ? { ...updated, seed: j.seed } : j))
              ))}
              envAvailable={catalog.env_status.PSALM_JURY_API_KEY ?? catalog.env_status.PSALM_API_KEY}
              providerPresets={catalog.provider_presets}
            />
            {jury.length > 3 && (
              <button type="button" onClick={() => removeJuror(index)}>Remove juror {index}</button>
            )}
          </div>
        ))}
        <button type="button" onClick={addJuror}>Add juror</button>
      </section>

      {submitError && <p role="alert">{submitError}</p>}
      <button type="button" onClick={handleSubmit} disabled={!canSubmit}>
        {submitting ? "Starting..." : "Start Trial"}
      </button>
    </div>
  );
}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `53 passed` (47 from Steps 1-5 plus 6 new)

- [ ] **Step 10: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 11: Commit**

```bash
git add examples/web/frontend/src/components/ examples/web/frontend/src/routes/SetupPage.tsx examples/web/frontend/src/routes/SetupPage.test.tsx examples/web/frontend/package.json examples/web/frontend/package-lock.json
git commit -m "feat: add AgentConfigPanel and the full SetupPage configuration form"
```

---

### Task 17: `LiveTrialPage`

**Files:**
- Create: `examples/web/frontend/src/routes/LiveTrialPage.tsx`
- Create: `examples/web/frontend/src/routes/LiveTrialPage.test.tsx`

**Interfaces:**
- Consumes: `useTrialStore` (Task 12), `TranscriptView`/`StageView`/`TimelineView` (Tasks 13-15).
- Produces: `LiveTrialPage.tsx`: `export default function LiveTrialPage(): JSX.Element` — reads `trialId` from the route (`react-router-dom`'s `useParams`), calls `startLive(trialId)` on mount, renders the dimension selector (only when 2+ dimensions are present) above the view tabs (default Stage), and navigates to `/trial/:trialId/result` once the trial's status becomes `"done"` or `"error"`.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/routes/LiveTrialPage.test.tsx`:

```tsx
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { PSALMEvent } from "../api/types";
import { useTrialStore } from "../state/store";
import LiveTrialPage from "./LiveTrialPage";

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
    expect(screen.getByText("Stage")).toHaveClass("active");
  });

  it("switching tabs changes the active view", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    act(() => {
      screen.getByText("Transcript").click();
    });
    expect(screen.getByText("Transcript")).toHaveClass("active");
  });

  it("shows a dimension selector only once 2+ dimensions are running", () => {
    let onEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, cb) => {
      onEvent = cb;
      return () => {};
    });
    renderAtTrial("abc123");
    expect(screen.queryByRole("button", { name: "Character" })).not.toBeInTheDocument();

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

    expect(screen.getByRole("button", { name: "Character" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plot" })).toBeInTheDocument();
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
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./LiveTrialPage"`

- [ ] **Step 3: Write `LiveTrialPage.tsx`**

Create `examples/web/frontend/src/routes/LiveTrialPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTrialStore } from "../state/store";
import StageView from "../views/StageView";
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
    if ((trialState.status === "done" || trialState.status === "error") && trialId) {
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
    <div className="live-trial-page">
      <h1>Trial in progress</h1>

      {trialState.dimensionOrder.length > 1 && (
        <div className="dimension-selector">
          {trialState.dimensionOrder.map((name) => (
            <button
              key={name}
              type="button"
              className={name === selectedDimension ? "active" : ""}
              onClick={() => setSelectedDimension(name)}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      <div className="view-tabs">
        {(Object.keys(VIEW_LABELS) as ViewName[]).map((view) => (
          <button
            key={view}
            type="button"
            className={view === activeView ? "active" : ""}
            onClick={() => setActiveView(view)}
          >
            {VIEW_LABELS[view]}
          </button>
        ))}
      </div>

      {activeView === "stage" && <StageView dimension={dimension} />}
      {activeView === "transcript" && (
        <TranscriptView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
      {activeView === "timeline" && (
        <TimelineView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `58 passed` (53 from Tasks 8-16 plus 5 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/LiveTrialPage.tsx examples/web/frontend/src/routes/LiveTrialPage.test.tsx
git commit -m "feat: add LiveTrialPage with dimension selector and view tabs"
```

---

### Task 18: `ResultsPage` — full structured report and Replay

**Files:**
- Create: `examples/web/frontend/src/routes/ResultsPage.tsx`
- Create: `examples/web/frontend/src/routes/ResultsPage.test.tsx`

**Interfaces:**
- Consumes: `getTrial` (Task 10), `useTrialStore` (Task 12), `StageView` (Task 14).
- Produces: `ResultsPage.tsx`: `export default function ResultsPage(): JSX.Element` — fetches the trial detail via `GET /api/trials/:id`, renders the verdict/rationale banner, a per-dimension score table, and a collapsible full argumentation/deliberation log per dimension built directly from the fetched `PSALMResult`. If the store still holds buffered live events for this trial (i.e. the user navigated here straight from `LiveTrialPage`), a "Replay this trial" button appears and switches into replay mode using `StageView` driven by the store's replay controller.

- [ ] **Step 1: Write the failing tests**

Create `examples/web/frontend/src/routes/ResultsPage.test.tsx`:

```tsx
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { PSALMEvent, TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import ResultsPage from "./ResultsPage";

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
    useTrialStore.setState({ allEvents: [{ type: "run_started" } as PSALMEvent] });
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");

    const replayButton = screen.getByText("Replay this trial");
    act(() => {
      replayButton.click();
    });
    expect(screen.getByText("Replay")).toBeInTheDocument();
  });

  it("does not show a Replay button when no live events were buffered (e.g. loaded from history)", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");
    expect(screen.queryByText("Replay this trial")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./ResultsPage"`

- [ ] **Step 3: Write `ResultsPage.tsx`**

Create `examples/web/frontend/src/routes/ResultsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getTrial } from "../api/client";
import type { TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import StageView from "../views/StageView";

export default function ResultsPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const [detail, setDetail] = useState<TrialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReplay, setShowReplay] = useState(false);
  const [replayDimension, setReplayDimension] = useState<string | null>(null);

  const liveEvents = useTrialStore((s) => s.allEvents);
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

  function startReplay() {
    loadForReplay(liveEvents);
    setShowReplay(true);
  }

  if (error) return <p role="alert">Failed to load trial: {error}</p>;
  if (!detail) return <p>Loading...</p>;

  const result = detail.result;

  return (
    <div className="results-page">
      <h1>Trial result</h1>
      {detail.status === "error" && <p role="alert">Trial failed: {detail.error_message}</p>}

      {result && (
        <>
          <section className="verdict-banner">
            <h2>Verdict: {result.verdict}</h2>
            <p>{result.rationale}</p>
          </section>

          <section>
            <h2>Per-dimension breakdown</h2>
            <table>
              <thead>
                <tr>
                  <th>Dimension</th><th>Type</th><th>Importance</th><th>Verdict</th><th>Score</th>
                </tr>
              </thead>
              <tbody>
                {result.dimension_verdicts.map((dv) => (
                  <tr key={dv.dimension}>
                    <td>{dv.dimension}</td>
                    <td>{dv.dimension_type}</td>
                    <td>{dv.importance}</td>
                    <td>{dv.verdict}</td>
                    <td>{dv.weighted_score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {result.dimension_verdicts.map((dv) => (
            <details key={dv.dimension}>
              <summary>{dv.dimension} — full log</summary>
              <h3>Argumentation</h3>
              {dv.argumentation_log.rounds.map((round) => (
                <div key={round.round}>
                  <h4>Round {round.round}</h4>
                  {round.prosecution_arguments.map((arg, i) => <p key={`pa${i}`}>Prosecution: {arg.claim}</p>)}
                  {round.prosecution_rejected_arguments.map((rej, i) => (
                    <p key={`pr${i}`}>Rejected (prosecution): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                  {round.defense_counters.map((arg, i) => <p key={`dc${i}`}>Defense counters: {arg.claim}</p>)}
                  {round.defense_counter_rejected_arguments.map((rej, i) => (
                    <p key={`dcr${i}`}>Rejected (defense counter): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                  {round.defense_arguments.map((arg, i) => <p key={`da${i}`}>Defense: {arg.claim}</p>)}
                  {round.defense_rejected_arguments.map((rej, i) => (
                    <p key={`dr${i}`}>Rejected (defense): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                  {round.prosecution_counters.map((arg, i) => (
                    <p key={`pc${i}`}>Prosecution counters: {arg.claim}</p>
                  ))}
                  {round.prosecution_counter_rejected_arguments.map((rej, i) => (
                    <p key={`pcr${i}`}>Rejected (prosecution counter): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                </div>
              ))}
              {dv.argumentation_log.prosecution_closing_argument && (
                <p>Prosecution closing: {dv.argumentation_log.prosecution_closing_argument}</p>
              )}
              {dv.argumentation_log.defense_closing_argument && (
                <p>Defense closing: {dv.argumentation_log.defense_closing_argument}</p>
              )}

              <h3>Deliberation</h3>
              {dv.debate_log.rounds.map((round) => (
                <div key={round.round}>
                  <h4>Round {round.round}</h4>
                  {round.votes.map((vote) => (
                    <p key={vote.juror_id}>{vote.juror_id}: {vote.vote} — {vote.rationale}</p>
                  ))}
                  {round.discussion_messages.map((msg, i) => (
                    <p key={i}>{msg.juror_id}: {msg.message}</p>
                  ))}
                </div>
              ))}
            </details>
          ))}
        </>
      )}

      {liveEvents.length > 0 && !showReplay && (
        <button type="button" onClick={startReplay}>Replay this trial</button>
      )}

      {showReplay && replayMode === "replay" && (
        <section className="replay-section">
          <h2>Replay</h2>
          {replayState.dimensionOrder.length > 1 && (
            <div className="dimension-selector">
              {replayState.dimensionOrder.map((name) => (
                <button
                  key={name} type="button"
                  className={name === replayDimension ? "active" : ""}
                  onClick={() => setReplayDimension(name)}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
          <div className="replay-controls">
            <button type="button" onClick={isPlaying ? pause : play}>{isPlaying ? "Pause" : "Play"}</button>
            <input
              type="range" min={-1} max={liveEvents.length - 1} value={replayIndex}
              onChange={(e) => scrubTo(Number(e.target.value))}
            />
          </div>
          <StageView dimension={replayDimension ? replayState.dimensions[replayDimension] ?? null : null} />
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `63 passed` (58 from Tasks 8-17 plus 5 new)

- [ ] **Step 5: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add examples/web/frontend/src/routes/ResultsPage.tsx examples/web/frontend/src/routes/ResultsPage.test.tsx
git commit -m "feat: add ResultsPage with full report and replay"
```

---

### Task 19: `HistoryPage` and final `App.tsx` routing

**Files:**
- Create: `examples/web/frontend/src/routes/HistoryPage.tsx`
- Create: `examples/web/frontend/src/routes/HistoryPage.test.tsx`
- Modify: `examples/web/frontend/src/App.tsx`
- Modify: `examples/web/frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `listTrials` (Task 10), `SetupPage`/`LiveTrialPage`/`ResultsPage` (Tasks 16-18).
- Produces: `HistoryPage.tsx`: `export default function HistoryPage(): JSX.Element` — lists every trial run this session, linking a still-`"running"` trial to `/trial/:id` and a finished one to `/trial/:id/result`. `App.tsx`: the real router, replacing Task 8's placeholder — `/` → `SetupPage`, `/trial/:trialId` → `LiveTrialPage`, `/trial/:trialId/result` → `ResultsPage`, `/trials` → `HistoryPage`. This is the last frontend task before backend integration (Task 20).

- [ ] **Step 1: Write the failing tests for `HistoryPage`**

Create `examples/web/frontend/src/routes/HistoryPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import HistoryPage from "./HistoryPage";

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

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npm run test`
Expected: FAIL — cannot resolve `"./HistoryPage"`

- [ ] **Step 3: Write `HistoryPage.tsx`**

Create `examples/web/frontend/src/routes/HistoryPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listTrials } from "../api/client";
import type { TrialSummary } from "../api/types";

export default function HistoryPage() {
  const [trials, setTrials] = useState<TrialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTrials().then(setTrials).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p role="alert">Failed to load trial history: {error}</p>;
  if (!trials) return <p>Loading...</p>;

  return (
    <div className="history-page">
      <h1>Trial history</h1>
      {trials.length === 0 && <p>No trials run yet this session.</p>}
      <ul>
        {trials.map((trial) => (
          <li key={trial.id}>
            <Link to={trial.status === "running" ? `/trial/${trial.id}` : `/trial/${trial.id}/result`}>
              {trial.created_at} — {trial.status}
              {trial.verdict && ` — ${trial.verdict}`}
            </Link>
            <p>{trial.source_text_preview} → {trial.target_text_preview}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `66 passed` (63 from Tasks 8-18 plus 3 new)

- [ ] **Step 5: Replace `App.tsx` with the real router**

Replace the contents of `examples/web/frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import HistoryPage from "./routes/HistoryPage";
import LiveTrialPage from "./routes/LiveTrialPage";
import ResultsPage from "./routes/ResultsPage";
import SetupPage from "./routes/SetupPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav className="app-nav">
        <Link to="/">New trial</Link>
        <Link to="/trials">History</Link>
      </nav>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/trial/:trialId" element={<LiveTrialPage />} />
        <Route path="/trial/:trialId/result" element={<ResultsPage />} />
        <Route path="/trials" element={<HistoryPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Update `App.test.tsx` for the real router**

Replace the contents of `examples/web/frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "./api/client";
import App from "./App";

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
});
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd examples/web/frontend && npm run test`
Expected: `66 passed` (the `App` test count stays the same — 1 test, rewritten — total unaffected by the rewrite itself)

- [ ] **Step 8: Verify the build still typechecks**

Run: `cd examples/web/frontend && npm run build`
Expected: no TypeScript errors

- [ ] **Step 9: Manually verify the app in dev mode**

Terminal 1: `uv run python examples/web/backend/main.py`
Terminal 2: `cd examples/web/frontend && npm run dev`

Open the printed dev server URL. Confirm: the Setup page loads with dimensions/presets from the real backend, filling in a preset and picking a dimension enables "Start Trial", and navigating to "History" shows an empty list before any trial has run. (A full trial run against a real LLM is verified in Task 20's integration pass — this step only confirms the frontend correctly talks to the real backend, not a mocked one.)

- [ ] **Step 10: Commit**

```bash
git add examples/web/frontend/src/routes/HistoryPage.tsx examples/web/frontend/src/routes/HistoryPage.test.tsx examples/web/frontend/src/App.tsx examples/web/frontend/src/App.test.tsx
git commit -m "feat: add HistoryPage and wire up the full app router"
```

---

## Part 3: Integration and documentation

### Task 20: Serve the built frontend from the backend (demo mode) + full manual walkthrough

**Files:**
- Modify: `examples/web/backend/main.py`

**Interfaces:**
- Consumes: `examples/web/frontend/dist/` (built by `npm run build` in Task 8/19).
- Produces: when `examples/web/frontend/dist/` exists, `main.py` serves it directly — any path not matched by an `/api/*` route returns the matching built file, or `index.html` as a fallback (so React Router's client-side routes like `/trial/abc123` work correctly on a hard refresh or direct navigation). When `dist/` doesn't exist (e.g. running backend tests in isolation), this route is never registered — no behavior change to anything from Tasks 1-7.

- [ ] **Step 1: Add the static-file fallback to `main.py`**

Add to `examples/web/backend/main.py`, after `app.include_router(api_router)` and the `/api/health` route, before the `if __name__ == "__main__":` block:

```python
from pathlib import Path

from fastapi.responses import FileResponse

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str) -> FileResponse:
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
```

(Move the `from pathlib import Path` and `from fastapi.responses import FileResponse` imports up to the top of the file alongside the existing imports, rather than leaving them inline.)

This catch-all is only registered when `dist/` exists on disk — checked once at import time — so it never interferes with any backend-only test run from Tasks 1-7 (none of which build the frontend first), and correctly does nothing until someone actually runs `npm run build`.

- [ ] **Step 2: Run the full backend test suite to confirm no regression**

Run: `uv run pytest examples/web/backend/tests/ -v && uv run ruff check examples/web/backend/`
Expected: all PASS (same count as Task 7), no lint errors — the new route is gated behind a directory-existence check that's false in the test environment (no `dist/` has been built there), so it never registers during these tests.

- [ ] **Step 3: Build the frontend and verify demo mode serves it**

```bash
cd examples/web/frontend && npm run build && cd ../../..
uv run python examples/web/backend/main.py &
curl -s http://127.0.0.1:8000/ | grep -o "<title>.*</title>"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/trial/some-fake-id
curl -s http://127.0.0.1:8000/api/health
kill %1
```

Expected: `<title>psalm courtroom demo</title>` from `/`; `200` from `/trial/some-fake-id` (the SPA fallback correctly serves `index.html` there, not a 404, so React Router can take over client-side); `{"status":"ok"}` from `/api/health` (proving `/api/*` routes still take priority over the catch-all).

- [ ] **Step 4: Full manual walkthrough with a real API key**

This step requires a real (or real-compatible, e.g. a local Ollama server exposing an OpenAI-compatible API) key, since it exercises actual LLM calls end to end — there is no automated equivalent, matching the spec's explicit "no end-to-end/browser automation in scope" decision (§6).

```bash
export PSALM_API_KEY="sk-..."
uv run python examples/web/backend/main.py
```

Open `http://127.0.0.1:8000` in a browser and walk through:
1. **Setup**: pick the "Infringing example" preset, select the Character dimension, leave all agent fields blank (relying on `PSALM_API_KEY`), click "Start Trial".
2. **Live trial**: confirm it navigates to `/trial/<id>`, the Stage view shows arguments/objections/votes appearing live, switching to the Transcript and Timeline tabs shows the same events in their respective layouts, and the page automatically navigates to the results page once the verdict is reached.
3. **Results**: confirm the verdict banner, per-dimension table, and expandable full argumentation/deliberation log (including any rejected arguments with the Judge's stated reason) are all populated. Click "Replay this trial" and confirm Play/Pause/scrub all work and reproduce the same sequence of events seen live.
4. **History**: navigate to "History" and confirm the just-completed trial appears, linking to its results page.
5. **Conflict check**: start a second trial from a second browser tab while the first is still running (or immediately re-submit before the first finishes) and confirm the UI surfaces the "a trial is already in progress" message rather than silently failing.

Fix any issues found before proceeding — this is the first point where the full stack has actually run together end to end.

- [ ] **Step 5: Commit**

```bash
git add examples/web/backend/main.py
git commit -m "feat: serve the built frontend from the backend in demo mode"
```

---

### Task 21: Finish `README.md` and final full-repo verification

**Files:**
- Modify: `examples/web/README.md`

**Interfaces:**
- Consumes: everything from Tasks 1-20.
- Produces: a complete `examples/web/README.md` covering both run modes, configuration, and the three views — the final deliverable of this plan.

- [ ] **Step 1: Rewrite `examples/web/README.md`**

Replace the contents of `examples/web/README.md`:

```markdown
# Courtroom Web Demo

A visual demo of `psalm`: configure a trial, watch it unfold live in a courtroom-themed
UI (three switchable views — Transcript, Stage, Timeline — driven by the SDK's realtime
event stream), and review the full transparent result afterward, with a scrubbable replay.

Local-only: one trial runs at a time, no auth, nothing persists past a backend restart.

## Running (demo mode — one command)

```bash
cd examples/web/frontend && npm install && npm run build && cd ../../..
uv run python examples/web/backend/main.py
```

Open http://127.0.0.1:8000 in a browser.

## Running (dev mode — frontend hot-reload)

Terminal 1:
```bash
uv run python examples/web/backend/main.py
```

Terminal 2:
```bash
cd examples/web/frontend
npm install
npm run dev
```

Open the URL Vite prints (typically http://localhost:5173) — it proxies API and SSE
requests to the backend on port 8000.

## Configuration

On the setup page, every agent (Prosecutor, Defense, Judge, each juror) can be configured
independently: provider (OpenAI, Azure OpenAI, Together.ai, Groq, or a custom
OpenAI-compatible endpoint), base URL, API key, model, and temperature. Any field left
blank falls back to the same environment variables `examples/cli/main.py` uses (see
`examples/cli/README.md` for the full 3-level fallback-chain reference: per-agent →
jury-wide → global), so you can e.g. set `PSALM_API_KEY` once and leave every field blank.

Note: like the rest of `psalm`, every agent talks to an OpenAI-compatible chat completions
API regardless of "provider" — the provider dropdown just pre-fills a known base URL, it
does not add support for a different SDK.

## The three live-trial views

- **Stage** (default) — a courtroom floor plan; a speech bubble appears over whoever is
  currently acting (Prosecutor, Defense, or a juror).
- **Transcript** — a scrolling, color-coded courtroom-transcript feed.
- **Timeline** — a phase stepper (Setup → Argumentation rounds → Deliberation → Verdict)
  alongside the transcript for the current phase.

Switch between them anytime with the tabs at the top — nothing is lost, they're all just
different views of the same live event stream. When 2+ dimensions are being evaluated, a
dimension selector appears above the view tabs to pick which one you're watching (the
others keep progressing in the background).

## Testing

Backend:
```bash
uv run pytest examples/web/backend/tests/ -v
uv run ruff check examples/web/backend/
```

Frontend:
```bash
cd examples/web/frontend
npm run test
npm run build   # also typechecks
```
```

- [ ] **Step 2: Run the entire project's test suite (SDK + backend) to confirm no regressions anywhere**

```bash
uv run pytest tests/ -q
uv run pytest examples/web/backend/tests/ -v
uv run ruff check psalm/ tests/ examples/web/backend/
cd examples/web/frontend && npm run test && npm run build
```

Expected: the main `psalm` SDK's suite passes exactly as it did before this plan (this plan never touched `psalm/`), the web backend suite passes in full, ruff is clean across both, and the frontend's tests and build both succeed.

- [ ] **Step 3: Commit**

```bash
git add examples/web/README.md
git commit -m "docs: finish the courtroom web demo README"
```

---

## Self-Review

**Spec coverage:**
- §2 architecture/layout → Tasks 1, 8 (backend/frontend directory skeletons), Task 20 (demo-mode single-command serving), Task 8 Step 9 / Task 19 Step 9 (dev-mode two-terminal serving). ✓
- §3.2 `GET /api/catalog` (dimensions, presets, evaluation strategies, provider presets, env status) → Task 3. ✓
- §3.3 `POST /api/trials` (fallback-chain resolution, 409/400 handling, background execution) → Tasks 2, 5. ✓
- §3.4 SSE with backlog replay + heartbeat → Task 6. ✓
- §3.5 trial store / history → Task 4 (store), Task 7 (`GET /api/trials`, `GET /api/trials/{id}`), Task 19 (`HistoryPage`). ✓
- §4.1 routes → Task 16 (`/`), Task 17 (`/trial/:id`), Task 18 (`/trial/:id/result`), Task 19 (`/trials` + final router). ✓
- §4.2 shared event-reducer model (live and replay use the same function) → Task 11 (`applyEvent`), Task 12 (store wiring both paths through it). ✓
- §4.3 multi-dimension selector, orthogonal to view choice → Task 17 (`LiveTrialPage`'s dimension selector sits above the view tabs, filtering all three identically). ✓
- §4.4 three views → Tasks 13-15. ✓
- §4.5 results page (from `PSALMResult`, not the event list) + replay (from the event list) → Task 18. ✓
- §4.6 setup form (presets, dimensions, advanced settings, per-agent config with env indicators, jury add/remove) → Task 16. ✓
- §5 error handling table → 409/400 (Task 5, surfaced in Task 16's `SetupPage`), mid-trial agent retry/failure (already-built SDK events, rendered by any view via Task 11's reducer), `RunFailed` (Task 11's `run_failed` case, surfaced in Task 18's error banner), reconnect-replays-backlog (Task 6's SSE design + Task 10's `EventSource` usage). ✓
- §6 testing (backend pytest, frontend Vitest/RTL, no e2e automation) → every task's own test file, explicitly scoped out of automation in Task 20 Step 4. ✓
- §7/§8/§9 no breaking changes to `psalm`/`examples/cli`, files table → verified in Task 21 Step 2 (full SDK suite unaffected) and matches every task's own file list above.

**Placeholder scan:** No "TBD"/"TODO"/vague-instruction phrases in any step; the one intentionally-manual verification (Task 20 Step 4) is explicitly justified (requires a real LLM key, matches the spec's own "no e2e automation" decision) rather than being a deferred placeholder.

**Type consistency:** `TrialConfigInput`/`AgentConfigInput`/`JurorConfigInput` (Task 9) match `TrialConfigRequest`/`AgentConfigRequest`/`JurorConfigRequest` (Task 4) field-for-field. `PSALMEvent`'s 20 members (Task 9) match the emission sites already built in the SDK (`docs/superpowers/specs/2026-07-12-realtime-event-streaming-design.md` §3) exactly, including `VotingStrategyApplied.verdict: string | null` and `JuryConsensusChecked.top_verdict: string | null` matching the corrected spec. `DimensionState`/`TrialState`/`TranscriptEntry` (Task 11) are used identically by `mergeTranscript` (Task 13), all three views (Tasks 13-15), and both live/results pages (Tasks 17-18) — no view or page redefines its own shape for this data. `useTrialStore`'s action names (`startLive`, `stopLive`, `reset`, `loadForReplay`, `play`, `pause`, `scrubTo`, `setReplaySpeed`) are used with identical names and argument shapes everywhere they're called (Tasks 17, 18).

---

Plan complete and saved to `docs/superpowers/plans/2026-07-12-courtroom-web-demo.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

