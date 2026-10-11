import io
import json
from datetime import date

import pytest

import fetch
import peopletray


def test_key_comes_from_env_first(tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text("label\nfile-key\n", encoding="utf-8")
    assert peopletray.load_key({"PT_API_KEY": " env-key "}, key_file) == "env-key"


def test_key_falls_back_to_line_2_of_the_file(tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text("﻿PT API Key for NMG\nfile-key\n", encoding="utf-8")
    assert peopletray.load_key({}, key_file) == "file-key"


def test_missing_key_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="PT_API_KEY"):
        peopletray.load_key({}, tmp_path / "absent.txt")


def test_get_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("PT_API_KEY", "k")
    calls, naps = [], []

    def opener(request, timeout):
        calls.append(request)
        if len(calls) < 3:
            raise OSError("connection reset")
        return io.BytesIO(json.dumps([{"a": 1}]).encode())

    result = peopletray.get("/api/v2/powerbi/events", {"fromDate": "2026-01-01"},
                            opener=opener, sleep=naps.append)
    assert result == [{"a": 1}]
    assert len(calls) == 3 and len(naps) == 2
    assert calls[0].full_url.endswith("/api/v2/powerbi/events?fromDate=2026-01-01")
    assert calls[0].get_header("X-api-key") == "k"


def test_get_gives_up_after_4_attempts(monkeypatch):
    monkeypatch.setenv("PT_API_KEY", "k")
    calls = []

    def opener(request, timeout):
        calls.append(request)
        raise OSError("down")

    with pytest.raises(RuntimeError, match="/api/v2/powerbi/people"):
        peopletray.get("/api/v2/powerbi/people", opener=opener, sleep=lambda s: None)
    assert len(calls) == 4


def test_fetch_all_window_and_keys():
    seen = []

    def fake_get(path, params=None):
        seen.append((path, params))
        return [{"path": path}]

    raw = fetch.fetch_all(date(2026, 10, 11), get=fake_get)
    assert set(raw) == {"events", "injuries", "hours", "actions", "people"}
    window = {"fromDate": "2024-11-01", "toDate": "2026-10-12"}
    assert ("/api/v2/powerbi/events", window) in seen
    assert ("/api/v2/powerbi/eventinjurylist", window) in seen
    assert ("/api/v2/powerbi/exposurehours", window) in seen
    assert ("/api/v2/powerbi/actions", window) in seen
    assert ("/api/v2/powerbi/people", None) in seen


def test_fetch_all_rejects_a_non_list_response():
    def fake_get(path, params=None):
        return {"message": "An error has occurred."} if path.endswith("exposurehours") else []

    with pytest.raises(ValueError, match="hours"):
        fetch.fetch_all(date(2026, 10, 11), get=fake_get)
