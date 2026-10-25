from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from broadcast import local_hub
from config import load_settings
from main import app
from pipeline import process_english_segment, translate_segment

BACKEND = Path(__file__).resolve().parents[1]
LINE = "Good morning, church. Let us pray."


def test_pipeline_fans_out_every_language() -> None:
    result = process_english_segment(LINE)
    assert result["captions"] == {
        "es": f"[es] {LINE}",
        "fr": f"[fr] {LINE}",
        "yo": f"[yo] {LINE}",
        "ig": f"[ig] {LINE}",
    }
    assert result["audio"] == {"es": True, "fr": True, "yo": False, "ig": False}
    events = {(lang, event) for lang, event, _payload in local_hub.events}
    assert ("es", "caption") in events
    assert ("es", "audio") in events
    assert ("yo", "caption") in events
    assert ("yo", "audio") not in events
    es_audio = next(payload for lang, event, payload in local_hub.events if lang == "es" and event == "audio")
    assert es_audio["content_type"] == "audio/wav"
    assert base64.b64decode(es_audio["audio_b64"])[:4] == b"RIFF"


def test_recognizer_translations_are_kept() -> None:
    captions = translate_segment(
        "Peace be with you",
        {"es": "La paz esté con ustedes", "fr": "La paix soit avec vous"},
    )
    assert captions["es"] == "La paz esté con ustedes"
    assert captions["fr"] == "La paix soit avec vous"
    assert captions["yo"] == "[yo] Peace be with you"
    assert captions["ig"] == "[ig] Peace be with you"


def test_health_languages_and_ingest_without_credentials() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "demo"
        assert body["run_mode"] == "demo"
        assert body["languages"] == ["es", "fr", "yo", "ig"]

        languages = client.get("/languages").json()
        assert languages["audio_and_captions"] == ["es", "fr"]
        assert languages["captions_only"] == ["yo", "ig"]

        page = client.get("/")
        assert page.status_code == 200
        assert "config.js" in page.text
        assert "hkackttlhowerfcvqwto" not in page.text

        config_js = client.get("/config.js")
        assert config_js.status_code == 200
        assert "service" not in config_js.text
        assert '"transport": "local"' in config_js.text

        ingested = client.post("/ingest", json={"text": LINE})
        assert ingested.status_code == 200
        assert ingested.json()["captions"]["ig"] == f"[ig] {LINE}"

        latest = client.get("/latest/es").json()
        assert latest["caption"]["text"] == f"[es] {LINE}"
        assert client.get("/latest/de").status_code == 404
        assert client.post("/ingest", json={"text": "   "}).status_code == 400
        assert client.post("/ingest", json={"text": ""}).status_code == 422


def test_websocket_renders_caption_then_audio() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/es") as socket:
            client.post("/ingest", json={"text": "Let us pray"})
            caption = socket.receive_json()
            audio = socket.receive_json()
        assert caption["event"] == "caption"
        assert caption["payload"]["text"] == "[es] Let us pray"
        assert audio["event"] == "audio"
        assert audio["payload"]["content_type"] == "audio/wav"
        assert base64.b64decode(audio["payload"]["audio_b64"])[:4] == b"RIFF"


def test_config_js_keeps_the_service_key_off_the_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "live")
    monkeypatch.setenv("INPUT_MODE", "text")
    monkeypatch.setenv("TRANSLATION_MODE", "mock")
    monkeypatch.setenv("BROADCAST_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://abccompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role-secret")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public-key")
    load_settings()
    with TestClient(app) as client:
        body = client.get("/config.js").text
    assert "anon-public-key" in body
    assert "service-role-secret" not in body
    assert "https://abccompany.supabase.co" in body


def test_live_mode_refuses_to_start_half_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "live")
    load_settings()
    with pytest.raises(RuntimeError, match="Live mode is not configured"):
        with TestClient(app):
            pass


def test_static_page_has_no_project_secrets() -> None:
    page = (BACKEND.parent / "frontend" / "output.html").read_text(encoding="utf-8")
    example = (BACKEND.parent / "frontend" / "config.example.js").read_text(encoding="utf-8")
    assert "hkackttlhowerfcvqwto" not in page
    assert "eyJ" not in page
    assert "service_role" not in page
    assert "YOUR-ANON-OR-PUBLISHABLE-KEY" in example
    assert "eyJ" not in example
    assert "config.js" in page
    assert "private: false" in page


def test_import_and_health_with_a_clean_environment() -> None:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("AZURE_") or key.startswith("SUPABASE_") or key in {
            "RUN_MODE",
            "INPUT_MODE",
            "TRANSLATION_MODE",
            "BROADCAST_MODE",
            "AUDIO_FILE",
            "TEXT_FILE",
        }:
            env.pop(key, None)
    env["PYTHONPATH"] = str(BACKEND)
    script = (
        "from fastapi.testclient import TestClient\n"
        "import main\n"
        "with TestClient(main.app) as client:\n"
        "    print(client.get('/health').json()['run_mode'])\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == "demo"
