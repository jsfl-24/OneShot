"""Tests for the static temp UI mounted at /ui."""


def test_ui_index_served(client):
    response = client.get("/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "OneShot" in response.text


def test_ui_assets_served(client):
    for asset in ("/ui/styles.css", "/ui/app.js"):
        response = client.get(asset)
        assert response.status_code == 200


def test_ui_assets_no_cache(client):
    for asset in ("/ui", "/ui/app.js", "/ui/styles.css"):
        response = client.get(asset)
        assert response.status_code == 200
        assert "no-cache" in response.headers["cache-control"]


def test_ui_mount_does_not_break_api(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ui_contains_workspace_markers(client):
    response = client.get("/ui")
    assert response.status_code == 200
    for marker in (
        'data-tab="shots"',
        'id="activity-console"',
        'id="task-card"',
        'id="project-constraints"',
        'id="btn-generate-all"',
    ):
        assert marker in response.text


def test_ui_javascript_uses_shot_and_constraint_endpoints(client):
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    for endpoint in ("/shots/generate", "/generate-shots-stream", "/constraints"):
        assert endpoint in response.text
    for function_marker in ("setActionState", "consumeSse", "data-tip"):
        assert function_marker in response.text


def test_ui_javascript_defines_api_helper(client):
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert "function api(" in response.text
