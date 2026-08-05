import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "database.db"
BOARD_JSON_PATH = Path(__file__).resolve().parent / "board.json"
DEFAULT_USER = {"username": "user", "password": "password"}

DEFAULT_BOARD = {
    "columns": [
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    "cards": {
        "card-1": {
            "id": "card-1",
            "title": "Align roadmap themes",
            "details": "Draft quarterly themes with impact statements and metrics.",
        },
        "card-2": {
            "id": "card-2",
            "title": "Gather customer signals",
            "details": "Review support tags, sales notes, and churn feedback.",
        },
        "card-3": {
            "id": "card-3",
            "title": "Prototype analytics view",
            "details": "Sketch initial dashboard layout and key drill-downs.",
        },
        "card-4": {
            "id": "card-4",
            "title": "Refine status language",
            "details": "Standardize column labels and tone across the board.",
        },
        "card-5": {
            "id": "card-5",
            "title": "Design card layout",
            "details": "Add hierarchy and spacing for scanning dense lists.",
        },
        "card-6": {
            "id": "card-6",
            "title": "QA micro-interactions",
            "details": "Verify hover, focus, and loading states.",
        },
        "card-7": {
            "id": "card-7",
            "title": "Ship marketing page",
            "details": "Final copy approved and asset pack delivered.",
        },
        "card-8": {
            "id": "card-8",
            "title": "Close onboarding sprint",
            "details": "Document release notes and share internally.",
        },
    },
}


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _load_default_board() -> dict[str, Any]:
    if BOARD_JSON_PATH.exists():
        try:
            return json.loads(BOARD_JSON_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return DEFAULT_BOARD


def init_db() -> None:
    connection = get_connection()
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        connection.execute(
            "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
            ("user", "password"),
        )

        user = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            ("user",),
        ).fetchone()

        if user is None:
            raise RuntimeError("Failed to initialize default user")

        existing_board = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user["id"],),
        ).fetchone()

        if existing_board is None:
            connection.execute(
                "INSERT INTO boards (user_id, data) VALUES (?, ?)",
                (user["id"], json.dumps(_load_default_board(), indent=2)),
            )

    connection.close()


def read_board(user_id: int = 1) -> dict[str, Any]:
    init_db()
    connection = get_connection()
    row = connection.execute(
        "SELECT data FROM boards WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    connection.close()

    if row is None:
        raise RuntimeError("Board state not found for user")

    return json.loads(row["data"])


def write_board(board_data: dict[str, Any], user_id: int = 1) -> dict[str, Any]:
    init_db()
    connection = get_connection()
    with connection:
        updated = connection.execute(
            "UPDATE boards SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (json.dumps(board_data, indent=2), user_id),
        )
        if updated.rowcount == 0:
            connection.execute(
                "INSERT INTO boards (user_id, data) VALUES (?, ?)",
                (user_id, json.dumps(board_data, indent=2)),
            )
    connection.close()
    return board_data
