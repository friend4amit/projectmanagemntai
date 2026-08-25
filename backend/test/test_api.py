import pytest
from fastapi.testclient import TestClient

from app import db, main
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


def test_new_board_starts_blank_not_copied_from_existing_board():
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        created = client.post("/api/boards", json={"title": "Second board"})
        board = client.get(f"/api/boards/{created.json()['id']}").json()
    assert board["cards"] == {}
    assert all(column["cardIds"] == [] for column in board["columns"])
    assert [column["title"] for column in board["columns"]] == ["Backlog", "Discovery", "In Progress", "Review", "Done"]


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


def test_static_fallback_rejects_path_traversal():
    with TestClient(app) as client:
        response = client.get("/..%2fmain.py")
    assert response.status_code == 200
    assert b"Project Management MVP Backend" not in response.content
    assert b"<!DOCTYPE html>" in response.content


def test_board_can_be_renamed():
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        board_id = client.get("/api/boards").json()[0]["id"]
        response = client.patch(f"/api/boards/{board_id}", json={"title": "Renamed board"})
        boards = client.get("/api/boards").json()
    assert response.status_code == 200
    assert response.json() == {"id": board_id, "title": "Renamed board"}
    assert boards[0]["title"] == "Renamed board"


def test_renaming_another_users_board_returns_404():
    with TestClient(app) as alice, TestClient(app) as bob:
        assert register(alice, "alice").status_code == 201
        alice_board_id = alice.get("/api/boards").json()[0]["id"]
        assert register(bob, "bob").status_code == 201
        response = bob.patch(f"/api/boards/{alice_board_id}", json={"title": "Hijacked"})
    assert response.status_code == 404


def test_board_can_be_deleted_when_another_board_exists():
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        first_board_id = client.get("/api/boards").json()[0]["id"]
        created = client.post("/api/boards", json={"title": "Second board"})
        response = client.delete(f"/api/boards/{created.json()['id']}")
        boards = client.get("/api/boards").json()
    assert response.status_code == 204
    assert [board["id"] for board in boards] == [first_board_id]


def test_deleting_the_only_board_is_rejected():
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        board_id = client.get("/api/boards").json()[0]["id"]
        response = client.delete(f"/api/boards/{board_id}")
        boards = client.get("/api/boards").json()
    assert response.status_code == 400
    assert len(boards) == 1


def test_deleting_another_users_board_returns_404():
    with TestClient(app) as alice, TestClient(app) as bob:
        assert register(alice, "alice").status_code == 201
        alice_board_id = alice.get("/api/boards").json()[0]["id"]
        assert register(bob, "bob").status_code == 201
        response = bob.delete(f"/api/boards/{alice_board_id}")
    assert response.status_code == 404


def test_ai_chat_requires_authentication():
    with TestClient(app) as client:
        response = client.post("/api/ai/chat", json={"prompt": "hi", "boardId": 1})
    assert response.status_code == 401


def test_ai_chat_returns_404_for_another_users_board():
    with TestClient(app) as alice, TestClient(app) as bob:
        assert register(alice, "alice").status_code == 201
        alice_board_id = alice.get("/api/boards").json()[0]["id"]
        assert register(bob, "bob").status_code == 201
        response = bob.post("/api/ai/chat", json={"prompt": "hi", "boardId": alice_board_id})
    assert response.status_code == 404


def test_ai_chat_returns_message_only_response(monkeypatch):
    monkeypatch.setattr(main, "call_openrouter", lambda prompt, board: {"message": "Board looks good.", "boardUpdate": None})
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        board_id = client.get("/api/boards").json()[0]["id"]
        response = client.post("/api/ai/chat", json={"prompt": "how does this look?", "boardId": board_id})
    assert response.status_code == 200
    assert response.json() == {"message": "Board looks good.", "boardUpdate": None}


def test_ai_chat_returns_board_update_action(monkeypatch):
    action = {"action": "moveCard", "cardId": "card-1", "toColumn": "col-done"}
    monkeypatch.setattr(main, "call_openrouter", lambda prompt, board: {"message": "Moved it.", "boardUpdate": action})
    with TestClient(app) as client:
        assert register(client, "alice").status_code == 201
        board_id = client.get("/api/boards").json()[0]["id"]
        response = client.post("/api/ai/chat", json={"prompt": "move card-1 to done", "boardId": board_id})
    assert response.status_code == 200
    assert response.json()["boardUpdate"] == action
