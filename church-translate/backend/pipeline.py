"""Turn one English line into captions and, for es/fr, audio."""

from __future__ import annotations

import concurrent.futures
from typing import Any

from broadcast import broadcast_audio, broadcast_caption
from config import AUDIO_LANGUAGES, CAPTION_ONLY_LANGUAGES
from translator_client import translate_text
from tts import synthesize

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="translate")


def translate_segment(
    source_text: str,
    speech_translations: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map each target language to a caption. Empty languages are omitted."""
    source_text = source_text.strip()
    if not source_text:
        return {}

    provided = {
        lang: text.strip()
        for lang, text in (speech_translations or {}).items()
        if text and text.strip()
    }
    captions: dict[str, str] = {}
    missing: list[str] = []
    for lang in AUDIO_LANGUAGES:
        if provided.get(lang):
            captions[lang] = provided[lang]
        else:
            missing.append(lang)
    missing.extend(CAPTION_ONLY_LANGUAGES.keys())

    if missing:
        translated = translate_text(source_text, missing)
        for lang in missing:
            text = (translated.get(lang) or "").strip()
            if text:
                captions[lang] = text
    return captions


def emit_segment(captions: dict[str, str]) -> dict[str, bool]:
    """Broadcast every caption, then audio for the speech languages.

    Captions go out before synthesis so the screen updates while TTS runs.
    """
    audio_sent = {lang: False for lang in captions}
    for lang, text in captions.items():
        broadcast_caption(lang, text)
    for lang, text in captions.items():
        if lang not in AUDIO_LANGUAGES:
            continue
        synthesized = synthesize(lang, text)
        if synthesized is None:
            continue
        audio_bytes, content_type = synthesized
        broadcast_audio(lang, audio_bytes, content_type)
        audio_sent[lang] = True
    return audio_sent


def process_english_segment(
    source_text: str,
    speech_translations: dict[str, str] | None = None,
) -> dict[str, Any]:
    captions = translate_segment(source_text, speech_translations)
    audio = emit_segment(captions) if captions else {}
    return {
        "source": source_text.strip(),
        "captions": captions,
        "audio": audio,
    }


def submit_segment(source_text: str, speech_translations: dict[str, str] | None = None) -> None:
    """Queue a segment from a Speech SDK callback without blocking recognition."""
    copied = dict(speech_translations or {})
    _executor.submit(process_english_segment, source_text, copied)
