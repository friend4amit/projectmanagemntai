import json
from urllib.error import HTTPError, URLError

import pytest

from app import ai


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(ai, "get_openrouter_api_key", lambda: "test-key")


class FakeResponse:
    """Minimal stand-in for the urlopen context manager, readable by json.load."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self, *args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_parse_response_text_with_clean_json():
    result = ai._parse_response_text('{"message": "Done.", "boardUpdate": null}')
    assert result == {"message": "Done.", "boardUpdate": None}


def test_parse_response_text_with_json_wrapped_in_prose():
    raw = 'Sure, here you go:\n{"message": "Moved the card.", "boardUpdate": {"action": "moveCard", "cardId": "card-1", "toColumn": "col-done"}}\nLet me know if you need more.'
    result = ai._parse_response_text(raw)
    assert result["message"] == "Moved the card."
    assert result["boardUpdate"] == {"action": "moveCard", "cardId": "card-1", "toColumn": "col-done"}


def test_parse_response_text_with_json_in_code_fence():
    raw = '```json\n{"message": "Renamed the column."}\n```'
    result = ai._parse_response_text(raw)
    assert result == {"message": "Renamed the column."}


def test_parse_response_text_with_malformed_json_falls_back_to_raw_text():
    raw = "This is not JSON at all, just prose."
    result = ai._parse_response_text(raw)
    assert result == {"message": raw, "boardUpdate": None}


def test_parse_response_text_with_empty_string():
    assert ai._parse_response_text("   ") == {"message": "No response received.", "boardUpdate": None}


def test_call_openrouter_without_api_key_returns_message(monkeypatch):
    monkeypatch.setattr(ai, "get_openrouter_api_key", lambda: None)
    result = ai.call_openrouter("hello", board=None)
    assert result["boardUpdate"] is None
    assert "OPENROUTER_API_KEY" in result["message"]


def test_call_openrouter_parses_successful_response(api_key, monkeypatch):
    payload = {"choices": [{"message": {"content": '{"message": "Hi there.", "boardUpdate": null}'}}]}
    monkeypatch.setattr(ai, "urlopen", lambda request, timeout: FakeResponse(payload))
    result = ai.call_openrouter("hi", board=None)
    assert result == {"message": "Hi there.", "boardUpdate": None}


def test_call_openrouter_handles_http_error(api_key, monkeypatch):
    def raise_http_error(request, timeout):
        raise HTTPError(url="http://example.com", code=401, msg="Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr(ai, "urlopen", raise_http_error)
    result = ai.call_openrouter("hi", board=None)
    assert result["boardUpdate"] is None
    assert "401" in result["message"]


def test_call_openrouter_handles_url_error(api_key, monkeypatch):
    def raise_url_error(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(ai, "urlopen", raise_url_error)
    result = ai.call_openrouter("hi", board=None)
    assert result["boardUpdate"] is None
    assert "connection refused" in result["message"]
