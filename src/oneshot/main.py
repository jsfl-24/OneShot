"""OneShot FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from oneshot.api import constraints, export, projects, providers, scenes, screenplays, shots
from oneshot.db import init_db


class NoCacheUIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not scope.get("path", "").startswith("/ui"):
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in {b"cache-control", b"pragma"}
                ]
                headers.extend(
                    [(b"cache-control", b"no-cache"), (b"pragma", b"no-cache")]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="OneShot", version="0.1.0", lifespan=lifespan)
app.add_middleware(NoCacheUIMiddleware)

app.include_router(projects.router)
app.include_router(screenplays.router)
app.include_router(scenes.router)
app.include_router(shots.router)
app.include_router(constraints.router)
app.include_router(export.router)
app.include_router(providers.router)

app.mount(
    "/ui",
    StaticFiles(directory=Path(__file__).parent / "ui", html=True),
    name="ui",
)


@app.get("/health")
def health():
    status = providers._status()
    return {
        "status": "ok",
        "llm": {
            "provider": status.llm.provider,
            "model": status.llm.model,
        },
        "embeddings": {
            "provider": status.embeddings.provider,
            "model": status.embeddings.model,
        },
    }