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
