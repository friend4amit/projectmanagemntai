import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "database.db"
BOARD_JSON_PATH = Path(__file__).resolve().parent / "board.json"
DEFAULT_USER = {"username": "user", "password": "password"}
DEFAULT_BOARD_TITLE = "My first board"

PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(digest.hex(), expected_hex)

DEFAULT_BOARD = {
    "columns": [
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    "cards": {
        "card-1": {"id": "card-1", "title": "Align roadmap themes", "details": "Draft quarterly themes with impact statements and metrics."},
        "card-2": {"id": "card-2", "title": "Gather customer signals", "details": "Review support tags, sales notes, and churn feedback."},
        "card-3": {"id": "card-3", "title": "Prototype analytics view", "details": "Sketch initial dashboard layout and key drill-downs."},
        "card-4": {"id": "card-4", "title": "Refine status language", "details": "Standardize column labels and tone across the board."},
        "card-5": {"id": "card-5", "title": "Design card layout", "details": "Add hierarchy and spacing for scanning dense lists."},
        "card-6": {"id": "card-6", "title": "QA micro-interactions", "details": "Verify hover, focus, and loading states."},
        "card-7": {"id": "card-7", "title": "Ship marketing page", "details": "Final copy approved and asset pack delivered."},
        "card-8": {"id": "card-8", "title": "Close onboarding sprint", "details": "Document release notes and share internally."},
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


def _blank_board() -> dict[str, Any]:
    columns = _load_default_board()["columns"]
    return {
        "columns": [{"id": column["id"], "title": column["title"], "cardIds": []} for column in columns],
        "cards": {},
    }


def _user_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "username": row["username"]}


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
                title TEXT NOT NULL DEFAULT 'My first board',
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        board_columns = {row["name"] for row in connection.execute("PRAGMA table_info(boards)")}
        if "title" not in board_columns:
            connection.execute(
                "ALTER TABLE boards ADD COLUMN title TEXT NOT NULL DEFAULT 'My first board'"
            )

        connection.execute(
            "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
            (DEFAULT_USER["username"], hash_password(DEFAULT_USER["password"])),
        )
        user = connection.execute(
            "SELECT id FROM users WHERE username = ?", (DEFAULT_USER["username"],)
        ).fetchone()
        if user is None:
            raise RuntimeError("Failed to initialize default user")
        if connection.execute("SELECT id FROM boards WHERE user_id = ?", (user["id"],)).fetchone() is None:
            connection.execute(
                "INSERT INTO boards (user_id, title, data) VALUES (?, ?, ?)",
                (user["id"], DEFAULT_BOARD_TITLE, json.dumps(_load_default_board(), indent=2)),
            )
    connection.close()


def create_user(username: str, password: str) -> dict[str, Any]:
    init_db()
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password))
            )
            user_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO boards (user_id, title, data) VALUES (?, ?, ?)",
                (user_id, DEFAULT_BOARD_TITLE, json.dumps(_load_default_board(), indent=2)),
            )
        return {"id": user_id, "username": username}
    except sqlite3.IntegrityError as exc:
        raise ValueError("Username is already in use") from exc
    finally:
        connection.close()


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    init_db()
    connection = get_connection()
    row = connection.execute(
        "SELECT id, username, password FROM users WHERE username = ?", (username,)
    ).fetchone()
    connection.close()
    if row is None or not verify_password(password, row["password"]):
        return None
    return _user_from_row(row)


def get_user(user_id: int) -> dict[str, Any] | None:
    connection = get_connection()
    row = connection.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    connection.close()
    return _user_from_row(row) if row else None


def list_boards(user_id: int) -> list[dict[str, Any]]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, title FROM boards WHERE user_id = ? ORDER BY updated_at DESC, id DESC", (user_id,)
    ).fetchall()
    connection.close()
    return [{"id": row["id"], "title": row["title"]} for row in rows]


def create_board(user_id: int, title: str) -> dict[str, Any]:
    connection = get_connection()
    with connection:
        cursor = connection.execute(
            "INSERT INTO boards (user_id, title, data) VALUES (?, ?, ?)",
            (user_id, title.strip(), json.dumps(_blank_board(), indent=2)),
        )
    board = {"id": cursor.lastrowid, "title": title.strip()}
    connection.close()
    return board


def read_board(user_id: int, board_id: int) -> dict[str, Any] | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT data FROM boards WHERE id = ? AND user_id = ?", (board_id, user_id)
    ).fetchone()
    connection.close()
    return json.loads(row["data"]) if row else None


def write_board(user_id: int, board_id: int, board_data: dict[str, Any]) -> bool:
    connection = get_connection()
    with connection:
        updated = connection.execute(
            "UPDATE boards SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (json.dumps(board_data, indent=2), board_id, user_id),
        )
    connection.close()
    return updated.rowcount > 0
