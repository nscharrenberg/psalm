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
