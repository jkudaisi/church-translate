"""
Text translation via Azure Translator.

Yoruba (`yo`) and Igbo (`ig`) are not Azure speech-translation languages.
The text Translator API does support both. Spanish and French use this same
call when the line did not already come from the speech recognizer (text
ingest, or a recognizer result that omitted a language).
"""

from __future__ import annotations

import json
import uuid
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests

from config import assert_never, get_settings

_DEFAULT_TIMEOUT_SECONDS = 8


def build_translate_url(endpoint: str, target_langs: list[str]) -> str:
    """Build the v3 translate URL for either the global or resource endpoint.

    Global:  https://api.cognitive.microsofttranslator.com/translate
    Resource: https://<name>.cognitiveservices.azure.com/translator/text/v3.0/translate
    """
    cleaned = endpoint.strip().rstrip("/")
    parts = urlsplit(cleaned)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"AZURE_TRANSLATOR_ENDPOINT is not a URL: {endpoint}")

    path = parts.path.rstrip("/")
    if not path.endswith("/translate"):
        host = parts.netloc.lower()
        if host.endswith("microsofttranslator.com"):
            path = f"{path}/translate" if path else "/translate"
        else:
            suffix = "/translator/text/v3.0/translate"
            path = f"{path}{suffix}" if path else suffix

    query = [("api-version", "3.0"), ("from", "en")]
    query.extend(("to", lang) for lang in target_langs)
    extra = urlencode(query)
    combined = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit((parts.scheme, parts.netloc, path, combined, ""))


def mock_translate(text: str, target_langs: list[str]) -> dict[str, str]:
    """Deterministic stand-in so the fan-out can be tested without Azure."""
    cleaned = text.strip()
    if not cleaned or not target_langs:
        return {}
    return {lang: f"[{lang}] {cleaned}" for lang in target_langs}


def translate_text(text: str, target_langs: list[str]) -> dict[str, str]:
    """Return {lang: translated_text}. Failures return {} and do not raise."""
    if not text.strip() or not target_langs:
        return {}

    settings = get_settings()
    mode = settings.translation_mode
    if mode == "mock":
        return mock_translate(text, target_langs)
    if mode == "azure":
        return _azure_translate(text, target_langs)
    assert_never(mode)


def _azure_translate(text: str, target_langs: list[str]) -> dict[str, str]:
    settings = get_settings()
    if not settings.azure_translator_key or not settings.azure_translator_region:
        print("[translator_client] missing translator key or region")
        return {}

    url = build_translate_url(settings.azure_translator_endpoint, target_langs)
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_translator_key,
        "Ocp-Apim-Subscription-Region": settings.azure_translator_region,
        "Content-Type": "application/json; charset=UTF-8",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    # The REST reference uses the capital-T "Text" field.
    body = json.dumps([{"Text": text}], ensure_ascii=False).encode("utf-8")

    try:
        response = requests.post(url, headers=headers, data=body, timeout=_DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        translations = data[0]["translations"]
        return {item["to"]: item["text"] for item in translations}
    except Exception as exc:  # noqa: BLE001 - keep the pipeline alive
        print(f"[translator_client] translation failed: {exc}")
        return {}
