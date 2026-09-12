"""API tests for project CRUD."""


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