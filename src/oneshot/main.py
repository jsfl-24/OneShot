from fastapi import FastAPI

from oneshot.api import screenplays, scenes, shots, export

app = FastAPI(title="OneShot", version="0.1.0")

app.include_router(screenplays.router)
app.include_router(scenes.router)
app.include_router(shots.router)
app.include_router(export.router)


@app.get("/health")
def health():
    return {"status": "ok"}
