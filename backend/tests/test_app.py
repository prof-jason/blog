import sqlite3

from fastapi.testclient import TestClient

from app.main import create_app


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_serves_static_frontend(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Prompt Generator" in response.text


def test_api_routes_take_precedence_over_static(client):
    assert client.get("/api/health").headers["content-type"].startswith("application/json")


def test_runs_without_a_frontend_build(db_path, tmp_path):
    with TestClient(create_app(db_path=db_path, static_dir=tmp_path / "missing")) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 404


def test_database_is_recreated_from_scratch_on_startup(db_path, static_dir):
    app = create_app(db_path=db_path, static_dir=static_dir)
    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"email": "a@example.com", "password": "password123"})
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1

    with TestClient(app):
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
