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
