"""OneShot FastAPI application."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from oneshot.api import constraints, export, projects, providers, scenes, screenplays, shots
from oneshot.config import settings
from oneshot.db import init_db
from oneshot.rag.ingest import seed_knowledge_if_needed

logger = logging.getLogger(__name__)


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


async def _rag_autoseed() -> None:
    """Seed the knowledge collection in the background; never raise."""
    try:
        report = await seed_knowledge_if_needed()
    except Exception:
        logger.warning(
            "RAG knowledge auto-seed failed; cinematic retrieval may be empty until "
            "the corpus is ingested. Rebuild manually with "
            "`python -m oneshot.rag.ingest --force`.",
            exc_info=True,
        )
        return

    if report is None:
        logger.debug("RAG knowledge collection already populated; skipping auto-seed")
        return

    logger.info(
        "RAG knowledge auto-seed stored %d chunks (%d embedded) in collection %s",
        report.chunks,
        report.embedded,
        report.collection,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    autoseed_task: asyncio.Task[None] | None = None
    if settings.RAG_AUTOSEED:
        autoseed_task = asyncio.create_task(_rag_autoseed(), name="rag-autoseed")
        app.state.rag_autoseed_task = autoseed_task

    try:
        yield
    finally:
        if autoseed_task is not None and not autoseed_task.done():
            autoseed_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await autoseed_task


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