from __future__ import annotations

import json

import pytest

from config import load_settings
from translator_client import build_translate_url, translate_text


def test_global_and_resource_endpoints() -> None:
    global_url = build_translate_url(
        "https://api.cognitive.microsofttranslator.com",
        ["yo", "ig"],
    )
    assert global_url == (
        "https://api.cognitive.microsofttranslator.com/translate"
        "?api-version=3.0&from=en&to=yo&to=ig"
    )

    resource_url = build_translate_url(
        "https://church-translator.cognitiveservices.azure.com/",
        ["es"],
    )
    assert resource_url == (
        "https://church-translator.cognitiveservices.azure.com"
        "/translator/text/v3.0/translate?api-version=3.0&from=en&to=es"
    )

    already = build_translate_url(
        "https://api.cognitive.microsofttranslator.com/translate",
        ["fr"],
    )
    assert already.count("/translate") == 1
    assert "from=en" in already
    assert "to=fr" in already


def test_mock_translation_is_marked() -> None:
    assert translate_text("Good morning", ["es", "yo"]) == {
        "es": "[es] Good morning",
        "yo": "[yo] Good morning",
    }
    assert translate_text("   ", ["es"]) == {}


def test_azure_request_matches_the_rest_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "live")
    monkeypatch.setenv("TRANSLATION_MODE", "azure")
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "translator-key")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "eastus")
    monkeypatch.setenv("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com")
    load_settings()

    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, object]]:
            return [{"translations": [{"to": "yo", "text": "Ẹ kú àárọ̀"}, {"to": "ig", "text": "Ụtụtụ ọma"}]}]

    def fake_post(url: str, headers: dict[str, str], data: bytes, timeout: int) -> _Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("translator_client.requests.post", fake_post)
    result = translate_text("Good morning", ["yo", "ig"])

    assert result == {"yo": "Ẹ kú àárọ̀", "ig": "Ụtụtụ ọma"}
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Content-Type"] == "application/json; charset=UTF-8"
    assert headers["Ocp-Apim-Subscription-Key"] == "translator-key"
    assert headers["Ocp-Apim-Subscription-Region"] == "eastus"
    assert json.loads(captured["data"]) == [{"Text": "Good morning"}]  # type: ignore[arg-type]
    assert "from=en" in str(captured["url"])
    assert "to=yo" in str(captured["url"])
    assert "to=ig" in str(captured["url"])


def test_azure_failure_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "live")
    monkeypatch.setenv("TRANSLATION_MODE", "azure")
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "translator-key")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "eastus")
    load_settings()

    def fake_post(*_args: object, **_kwargs: object) -> None:
        raise OSError("offline")

    monkeypatch.setattr("translator_client.requests.post", fake_post)
    assert translate_text("Hello", ["yo"]) == {}
