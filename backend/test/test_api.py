from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ping():
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "pong"}


def test_get_board():
    response = client.get("/api/board")
    assert response.status_code == 200
    data = response.json()
    assert "columns" in data
    assert "cards" in data


def test_put_board():
    response = client.get("/api/board")
    board = response.json()
    board["columns"][0]["title"] = "Backlog Updated"

    put_response = client.put("/api/board", json=board)
    assert put_response.status_code == 200
    assert put_response.json()["columns"][0]["title"] == "Backlog Updated"


def test_logout():
    response = client.post("/api/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "signed out"}


def test_ai_chat():
    response = client.post("/api/ai/chat", json={"prompt": "Say hello"})
    assert response.status_code == 200
    assert response.json()["message"]
    assert "boardUpdate" in response.json()
