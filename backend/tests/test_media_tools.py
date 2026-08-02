"""Manifest (de)serialization helpers. Offline — no B2, no providers, no cost."""
import json

import pytest


def test_manifest_from_json_decodes_before_parsing(monkeypatch):
    """parse_manifest takes a dict; handing it raw JSON text used to AttributeError."""
    from app import media_tools

    seen = {}
    monkeypatch.setattr(media_tools, "parse_manifest", lambda data: seen.setdefault("data", data))
    payload = {"schema_version": "1.0", "run_id": "r1"}

    media_tools.manifest_from_json(json.dumps(payload))

    assert seen["data"] == payload
    assert isinstance(seen["data"], dict)


def test_manifest_from_json_rejects_malformed_json(monkeypatch):
    from app import media_tools

    monkeypatch.setattr(media_tools, "parse_manifest", lambda data: data)

    with pytest.raises(json.JSONDecodeError):
        media_tools.manifest_from_json("not json{")
