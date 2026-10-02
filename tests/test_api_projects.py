"""API tests for project CRUD."""

from pathlib import Path

from sqlalchemy import func, select
from sqlmodel import Session, create_engine

from oneshot.config import settings
from oneshot.db_models import ProductionConstraints, Scene, Screenplay, Shot


def _count(session, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return session.exec(statement).one()[0]


def test_create_project(client):
    resp = client.post("/projects", json={"name": "My Film", "description": "A test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Film"
    assert data["description"] == "A test"
    assert "id" in data


def test_list_projects_empty(client):
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_projects(client):
    client.post("/projects", json={"name": "Film A"})
    client.post("/projects", json={"name": "Film B"})

    resp = client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_project_found(client):
    created = client.post("/projects", json={"name": "Film A"}).json()
    resp = client.get(f"/projects/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Film A"


def test_get_project_not_found(client):
    resp = client.get("/projects/999")
    assert resp.status_code == 404


def test_delete_project(client):
    created = client.post("/projects", json={"name": "Film A"}).json()

    resp = client.delete(f"/projects/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"id": created["id"], "deleted": True}

    assert client.get("/projects").json() == []
    assert client.get(f"/projects/{created['id']}").status_code == 404


def test_delete_project_not_found(client):
    resp = client.delete("/projects/999")
    assert resp.status_code == 404


def test_delete_project_cascade(client, tmp_path, sample_screenplay_path):
    project_id = client.post("/projects", json={"name": "Film A"}).json()["id"]

    with sample_screenplay_path.open("rb") as handle:
        upload = client.post(
            f"/screenplays/projects/{project_id}/upload",
            files={"file": (sample_screenplay_path.name, handle, "text/plain")},
        )
    assert upload.status_code == 200
    source_path = upload.json()["source_path"]
    assert (settings.UPLOAD_DIR).is_dir()
    assert list(settings.UPLOAD_DIR.iterdir())

    resp = client.delete(f"/projects/{project_id}")
    assert resp.status_code == 200
    assert client.get("/projects").json() == []

    assert not Path(source_path).exists()

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    with Session(engine) as session:
        screenplay_ids = session.exec(
            select(Screenplay.id).where(Screenplay.project_id == project_id)
        ).all()
        scene_ids = session.exec(
            select(Scene.id).where(Scene.project_id == project_id)
        ).all()
        counts = {
            "screenplays": _count(session, Screenplay, Screenplay.project_id == project_id),
            "scenes": _count(session, Scene, Scene.project_id == project_id),
            "shots": _count(session, Shot),
            "production_constraints": _count(
                session, ProductionConstraints, ProductionConstraints.project_id == project_id
            ),
        }
    engine.dispose()

    assert screenplay_ids == []
    assert scene_ids == []
    assert all(count == 0 for count in counts.values()), counts
