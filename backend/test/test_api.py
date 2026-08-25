import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, sessions


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    sessions.clear()
    db.init_db()


def register(client: TestClient, username: str, password: str = "password"):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def test_ping():
    with TestClient(app) as client:
        response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "pong"}


def test_default_user_can_log_in_and_has_a_board():
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": "user", "password": "password"})
        boards = client.get("/api/boards")
    assert response.status_code == 200
    assert boards.status_code == 200
    assert len(boards.json()) == 1


def test_user_can_create_and_update_multiple_boards():
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        initial_boards = client.get("/api/boards").json()
        created = client.post("/api/boards", json={"title": "Launch plan"})
        boards = client.get("/api/boards").json()
        board = client.get(f"/api/boards/{created.json()['id']}").json()
        board["columns"][0]["title"] = "Ideas"
        saved = client.put(f"/api/boards/{created.json()['id']}", json=board)
        original = client.get(f"/api/boards/{initial_boards[0]['id']}").json()
    assert created.status_code == 201
    assert len(boards) == 2
    assert saved.json()["columns"][0]["title"] == "Ideas"
    assert original["columns"][0]["title"] == "Backlog"


def test_users_cannot_access_each_others_boards():
    with TestClient(app) as alice, TestClient(app) as bob:
        assert register(alice, "alice").status_code == 201
        alice_board_id = alice.get("/api/boards").json()[0]["id"]
        assert register(bob, "bob").status_code == 201
        response = bob.get(f"/api/boards/{alice_board_id}")
    assert response.status_code == 404


def test_logout_revokes_the_session():
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        assert client.post("/api/logout").status_code == 200
        response = client.get("/api/boards")
    assert response.status_code == 401
