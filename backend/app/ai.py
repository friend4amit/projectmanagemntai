import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT = 30


def _message_only(message: str) -> dict[str, Any]:
    return {"message": message, "boardUpdate": None}


def _load_dotenv_if_present() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip()


def get_openrouter_api_key() -> str | None:
    _load_dotenv_if_present()
    return os.getenv("OPENROUTER_API_KEY")


def _format_assistant_prompt(prompt: str, board: dict[str, Any] | None) -> str:
    lines = [
        "You are an assistant for a kanban board application.",
        "Respond with valid JSON only.",
        "The JSON object should contain a 'message' string and an optional 'boardUpdate' object.",
        "If no board changes are needed, return only 'message'.",
        "When a change is needed, 'boardUpdate' must be one of these exact shapes:",
        '  - Move a card: {"action": "moveCard", "cardId": "<card id>", "toColumn": "<column id or title>"}',
        '  - Create a card: {"action": "createCard", "card": {"title": "<title>", "description": "<details>", "column": "<column id or title>"}}',
        '  - Rename a column: {"action": "renameColumn", "columnId": "<column id>", "title": "<new title>"}',
        "  - Or a full board replacement with the complete 'columns' and 'cards' as given in the current board state.",
        "Never return a partial 'columns' list without the matching action field above.",
    ]
    if board is not None:
        lines.append("Current board state:")
        lines.append(json.dumps(board, indent=2))
    lines.append("User request:")
    lines.append(prompt)
    lines.append("Return only JSON.")
    return "\n".join(lines)


def _parse_response_text(raw_text: str) -> dict[str, Any]:
    """Models often wrap their JSON in prose or code fences, so pull out the first {...} block."""
    cleaned = raw_text.strip()
    if not cleaned:
        return _message_only("No response received.")

    json_start = cleaned.find("{")
    json_end = cleaned.rfind("}")
    if json_start != -1 and json_end != -1 and json_end > json_start:
        candidate = cleaned[json_start : json_end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return _message_only(cleaned)


def _extract_completion_text(response_data: dict[str, Any]) -> str | None:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None

    message = first_choice.get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(first_choice.get("text"), str):
        return first_choice["text"].strip()
    return None


def call_openrouter(prompt: str, board: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = get_openrouter_api_key()
    if not api_key:
        return _message_only("OPENROUTER_API_KEY is not configured. Set it in the environment or .env file.")

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": "You are a kanban board assistant. Respond in JSON with message and optional boardUpdate."},
            {"role": "user", "content": _format_assistant_prompt(prompt, board)},
        ],
        "temperature": 0.2,
    }

    request = Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            response_data = json.load(response)
    except HTTPError as exc:
        return _message_only(f"OpenRouter request failed: {exc.code} {exc.reason}")
    except URLError as exc:
        return _message_only(f"OpenRouter request failed: {exc.reason}")
    except Exception as exc:
        return _message_only(f"OpenRouter request failed: {exc}")

    completion_text = _extract_completion_text(response_data)
    if completion_text is None:
        return _message_only(json.dumps(response_data))
    return _parse_response_text(completion_text)
