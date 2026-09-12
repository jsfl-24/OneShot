from contextlib import asynccontextmanager

from fastapi import FastAPI

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