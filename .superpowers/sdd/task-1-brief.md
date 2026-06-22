# Task 1 Brief: Project Scaffold

## Context
You are implementing Task 1 of the psalm-eu v2.0.0 Foundation Plan.
This is the first task — no prior code exists except a placeholder `main.py` and an empty `pyproject.toml`.
Project root: `C:\Users\P70098761\Documents\projects\psalm-mirror`
Branch: `v2`

## Requirements (implement exactly as specified)

### Files to create/modify:
- Modify: `pyproject.toml` (replace entirely)
- Create empty `__init__.py` in: `psalm/`, `psalm/models/`, `psalm/agents/`, `psalm/phases/`, `psalm/voting/`, `psalm/courtroom/`, `psalm/communication/`
- Create empty `__init__.py` in: `tests/`, `tests/unit/`, `tests/unit/models/`, `tests/integration/`, `tests/e2e/`

### Step 1: Replace `pyproject.toml` with exactly this content:

```toml
[project]
name = "psalm-eu"
version = "2.0.0"
description = "Courtroom-inspired multi-agent system for EU copyright infringement evaluation"
requires-python = ">=3.14"
dependencies = [
    "langgraph>=1.2.6",
    "langchain>=1.3.10",
    "langchain-openai>=0.3.0",
    "pydantic>=2.13.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.1.1",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.15.18",
    "ty>=0.0.51",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Step 2: Create all directories and empty `__init__.py` files listed above.

### Step 3: Run `uv sync --extra dev` to install dependencies.

### Step 4: Verify with:
```
uv run python -c "import psalm; import pydantic; import langgraph; print('OK')"
```
Expected output: `OK`

Also run: `uv run pytest` — expected: 0 tests collected, no errors.

### Step 5: Commit with message: `chore: scaffold psalm-eu package structure`

## Global Constraints
- `requires-python = ">=3.14"`
- Package name: `psalm-eu`, version `2.0.0`
- `uv` is the package manager
- Do NOT create any Python source files beyond empty `__init__.py` files

## Report
Write your full report to: `C:\Users\P70098761\Documents\projects\psalm-mirror\.superpowers\sdd\task-1-report.md`

Return only:
- Status: DONE / BLOCKED / NEEDS_CONTEXT
- Commit hash(es)
- One-line test summary
- Any concerns
