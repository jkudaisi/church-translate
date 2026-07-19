"""
Text-only translation via Azure Translator.
Used for Yoruba and Igbo, which Azure Speech cannot translate directly
(neither language is in Azure's speech-to-text / speech-translation locale list).
"""
import uuid
import requests

from config import AZURE_TRANSLATOR_KEY, AZURE_TRANSLATOR_REGION, AZURE_TRANSLATOR_ENDPOINT

_TRANSLATE_PATH = "/translate?api-version=3.0"


def translate_text(text: str, target_langs: list[str]) -> dict[str, str]:
    """
    Translate `text` (English) into each language code in `target_langs`.
    Returns {lang_code: translated_text}. Returns {} on failure (caller should
    just skip broadcasting captions for this segment rather than crash the pipeline).
    """
    if not text.strip() or not target_langs:
        return {}

    params = "&".join(f"to={lang}" for lang in target_langs)
    url = f"{AZURE_TRANSLATOR_ENDPOINT}{_TRANSLATE_PATH}&{params}"

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    body = [{"text": text}]

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        translations = data[0]["translations"]
        return {t["to"]: t["text"] for t in translations}
    except Exception as exc:  # noqa: BLE001 - log and keep the pipeline alive
        print(f"[translator_client] translation failed: {exc}")
        return {}
