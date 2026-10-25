from __future__ import annotations

import base64
import io
import json
import wave

import pytest

from broadcast import FREE_PLAN_PAYLOAD_BYTES, build_broadcast_url, broadcast_caption, local_hub
from config import load_settings
from tts import WAV_CONTENT_TYPE, synthesize


def test_mock_audio_is_a_wav_the_browser_can_decode() -> None:
    synthesized = synthesize("es", "Good morning, church")
    assert synthesized is not None
    audio, content_type = synthesized
    assert content_type == WAV_CONTENT_TYPE
    assert audio[:4] == b"RIFF"
    with wave.open(io.BytesIO(audio), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() > 0


def test_caption_only_language_has_no_audio() -> None:
    assert synthesize("yo", "Good morning") is None


def test_broadcast_url_is_public_and_uses_the_bare_topic() -> None:
    url = build_broadcast_url(
        "https://abccompany.supabase.co",
        "church-translate:es",
        "caption",
        private=False,
    )
    assert url == (
        "https://abccompany.supabase.co/realtime/v1/api/broadcast/"
        "church-translate%3Aes/events/caption"
    )
    assert "realtime%3A" not in url
    assert "private" not in url

    private_url = build_broadcast_url(
        "https://abccompany.supabase.co/",
        "church-translate:fr",
        "audio",
        private=True,
    )
    assert private_url.endswith("?private=true")


def test_supabase_post_uses_the_service_key_and_raw_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "live")
    monkeypatch.setenv("INPUT_MODE", "text")
    monkeypatch.setenv("TRANSLATION_MODE", "mock")
    monkeypatch.setenv("BROADCAST_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://abccompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role-secret")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public")
    load_settings()

    captured: dict[str, object] = {}

    class _Response:
        status_code = 202
        text = ""

    def fake_post(url: str, headers: dict[str, str], data: bytes, timeout: int) -> _Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("broadcast.requests.post", fake_post)
    broadcast_caption("es", "Hola")

    assert captured["url"] == (
        "https://abccompany.supabase.co/realtime/v1/api/broadcast/"
        "church-translate%3Aes/events/caption"
    )
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["apikey"] == "service-role-secret"
    assert headers["Authorization"] == "Bearer service-role-secret"
    body = json.loads(captured["data"])  # type: ignore[arg-type]
    assert body["text"] == "Hola"
    assert "payload" not in body
    assert local_hub.caption_snapshot("es")["text"] == "Hola"
    assert FREE_PLAN_PAYLOAD_BYTES == 256 * 1024


def test_demo_broadcast_does_not_call_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_post(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("demo mode must not call Supabase")

    monkeypatch.setattr("broadcast.requests.post", fail_post)
    broadcast_caption("fr", "Bonjour")
    assert local_hub.caption_snapshot("fr")["text"] == "Bonjour"


def test_round_trip_base64_audio() -> None:
    synthesized = synthesize("fr", "Bonjour")
    assert synthesized is not None
    audio, content_type = synthesized
    encoded = base64.b64encode(audio).decode("ascii")
    assert base64.b64decode(encoded)[:4] == b"RIFF"
    assert content_type == "audio/wav"
