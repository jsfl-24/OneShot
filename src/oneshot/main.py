"""OneShot FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from oneshot.api import export, projects, scenes, screenplays, shots
from oneshot.config import settings
from oneshot.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="OneShot", version="0.1.0", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(screenplays.router)
app.include_router(scenes.router)
app.include_router(shots.router)
app.include_router(export.router)

app.mount(
    "/ui",
    StaticFiles(directory=Path(__file__).parent / "ui", html=True),
    name="ui",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
        },
        "embeddings": {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL,
        },
    }