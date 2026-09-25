"""API tests for production constraints (project defaults + per-scene overrides)."""

from oneshot.schemas import CameraMovement


def _setup(client):
    project = client.post("/projects", json={"name": "P"}).json()
    with open("tests/fixtures/sample_screenplay.txt", "rb") as fh:
        upload = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("sample.txt", fh, "text/plain")},
        ).json()
    scene_id = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"][0]["id"]
    return project, upload, scene_id


def test_project_constraints_roundtrip(client):
    project, _, _ = _setup(client)
    payload = {
        "camera_movement_allowed": ["Static", "Dolly"],
        "high_angle_possible": True,
        "available_lenses": ["50mm", "85mm"],
    }
    put = client.put(f"/projects/{project['id']}/constraints", json=payload)
    assert put.status_code == 200
    assert put.json()["high_angle_possible"] is True

    got = client.get(f"/projects/{project['id']}/constraints").json()
    assert got["available_lenses"] == ["50mm", "85mm"]
    assert got["camera_movement_allowed"] == ["Static", "Dolly"]


def test_project_constraints_defaults_when_absent(client):
    project, _, _ = _setup(client)
    got = client.get(f"/projects/{project['id']}/constraints").json()
    assert got["available_lenses"] == ["50mm"]
    assert got["high_angle_possible"] is False


def test_scene_constraints_override_project(client):
    project, _, scene_id = _setup(client)
    client.put(
        f"/projects/{project['id']}/constraints",
        json={"available_lenses": ["50mm", "85mm"], "high_angle_possible": True},
    )
    put = client.put(
        f"/projects/{project['id']}/scenes/{scene_id}/constraints",
        json={"available_lenses": ["85mm"]},
    )
    assert put.status_code == 200

    merged = client.get(f"/projects/{project['id']}/scenes/{scene_id}/constraints").json()
    assert merged["available_lenses"] == ["85mm"]
    assert merged["high_angle_possible"] is True


def test_scene_constraint_null_clears_override_and_inherits_project(client):
    project, _, scene_id = _setup(client)
    project_constraints_url = f"/projects/{project['id']}/constraints"
    scene_constraints_url = (
        f"/projects/{project['id']}/scenes/{scene_id}/constraints"
    )

    project_put = client.put(
        project_constraints_url,
        json={"available_lenses": ["85mm"], "high_angle_possible": True},
    )
    assert project_put.status_code == 200

    scene_put = client.put(scene_constraints_url, json={"available_lenses": ["35mm"]})
    assert scene_put.status_code == 200

    merged = client.get(scene_constraints_url).json()
    assert merged["available_lenses"] == ["35mm"]
    assert merged["high_angle_possible"] is True

    clear_put = client.put(scene_constraints_url, json={"available_lenses": None})
    assert clear_put.status_code == 200

    merged = client.get(scene_constraints_url).json()
    assert merged["available_lenses"] == ["85mm"]
    assert merged["high_angle_possible"] is True


def test_constraints_404_on_missing_resources(client):
    missing_project = client.put("/projects/999999/constraints", json={})
    assert missing_project.status_code == 404

    project, _, _scene_id = _setup(client)
    missing_scene = client.put(
        f"/projects/{project['id']}/scenes/999999/constraints", json={}
    )
    assert missing_scene.status_code == 404


def test_constraints_enforce_camera_movement_enum(client):
    project, _, _ = _setup(client)
    response = client.put(
        f"/projects/{project['id']}/constraints",
        json={"camera_movement_allowed": ["Crane"]},
    )
    assert response.status_code == 200
    assert response.json()["camera_movement_allowed"] == [CameraMovement.CRANE.value]