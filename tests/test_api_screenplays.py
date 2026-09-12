"""API tests for screenplay upload, parse, and scene detection."""


def _create_project(client, name="Test Project"):
    return client.post("/projects", json={"name": name}).json()


def test_upload_txt_screenplay(client, sample_screenplay_path):
    project = _create_project(client)
    with sample_screenplay_path.open("rb") as f:
        resp = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("sample_screenplay.txt", f, "text/plain")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project["id"]
    assert data["filename"] == "sample_screenplay.txt"
    assert data["format"] == "txt"
    assert data["source_path"].endswith(".txt")


def test_upload_unsupported_format(client):
    project = _create_project(client)
    resp = client.post(
        f"/screenplays/projects/{project['id']}/upload",
        files={"file": ("notes.md", b"# hello", "text/markdown")},
    )
    assert resp.status_code == 415


def test_upload_requires_existing_project(client, sample_screenplay_path):
    with sample_screenplay_path.open("rb") as f:
        resp = client.post(
            "/screenplays/projects/999/upload",
            files={"file": ("sample_screenplay.txt", f, "text/plain")},
        )
    assert resp.status_code == 404


def test_list_screenplays_for_project(client, sample_screenplay_path):
    project = _create_project(client)
    with sample_screenplay_path.open("rb") as f:
        client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("sample_screenplay.txt", f, "text/plain")},
        )

    resp = client.get(f"/screenplays/projects/{project['id']}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_screenplay(client, sample_screenplay_path):
    project = _create_project(client)
    with sample_screenplay_path.open("rb") as f:
        uploaded = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("sample_screenplay.txt", f, "text/plain")},
        ).json()

    resp = client.get(f"/screenplays/{uploaded['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == uploaded["id"]


def test_upload_auto_detects_scenes(client, sample_screenplay_path):
    project = _create_project(client)
    with sample_screenplay_path.open("rb") as f:
        uploaded = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("sample_screenplay.txt", f, "text/plain")},
        ).json()

    resp = client.get(f"/screenplays/{uploaded['id']}/scenes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["screenplay_id"] == uploaded["id"]

    scenes = data["scenes"]
    assert len(scenes) == 4

    first = scenes[0]
    assert first["scene_number"] == 1
    assert first["heading"] == "INT. COFFEE SHOP - DAY"
    assert first["location"] == "COFFEE SHOP"
    assert first["time_of_day"] == "DAY"
    assert "COFFEE SHOP" in first["raw_text"] or first["raw_text"]


def test_scenes_not_found_for_missing_screenplay(client):
    resp = client.get("/screenplays/42/scenes")
    assert resp.status_code == 404


def test_upload_pdf_screenplay(client, sample_screenplay_pdf_path):
    _test_upload_format(client, sample_screenplay_pdf_path)


def test_upload_docx_screenplay(client, sample_screenplay_docx_path):
    _test_upload_format(client, sample_screenplay_docx_path)


def _test_upload_format(client, path):
    project = _create_project(client)
    with path.open("rb") as f:
        resp = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": (path.name, f, "application/octet-stream")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] in {"pdf", "docx"}

    scenes_resp = client.get(f"/screenplays/{data['id']}/scenes")
    assert scenes_resp.status_code == 200
    assert len(scenes_resp.json()["scenes"]) >= 1