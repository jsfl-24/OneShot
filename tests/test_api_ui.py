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


def test_ui_mount_does_not_break_api(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"