"""Runtime settings.

Missing or placeholder credentials start demo mode. Importing this module
does not require Azure or Supabase, so `uvicorn main:app` can boot for a
sound check.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never, cast

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"

# Speech-translation + neural TTS. Codes are what TranslationRecognizer
# expects (language, not a full locale). Voice names are current Azure
# neural voices: es-ES-ElviraNeural, fr-FR-DeniseNeural.
AUDIO_LANGUAGES: dict[str, str] = {
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
}

# No Azure speech-translation or neural TTS voice. Text Translator supports both.
CAPTION_ONLY_LANGUAGES: dict[str, str] = {
    "yo": "Yoruba",
    "ig": "Igbo",
}

ALL_LANGUAGES: dict[str, str] = {
    **{code: code for code in AUDIO_LANGUAGES},
    **CAPTION_ONLY_LANGUAGES,
}

RunMode = Literal["demo", "live"]
InputMode = Literal["text", "microphone", "file"]
TranslationMode = Literal["mock", "azure"]
BroadcastMode = Literal["local", "supabase"]

_SECRET_ENV_VARS = (
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
    "AZURE_SPEECH_ENDPOINT",
    "AZURE_TRANSLATOR_KEY",
    "AZURE_TRANSLATOR_REGION",
    "AZURE_TRANSLATOR_ENDPOINT",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_ANON_KEY",
)


def assert_never(value: Never) -> None:
    raise RuntimeError(f"unhandled value: {value!r}")


def _raw(name: str) -> str:
    return os.environ.get(name, "").strip()


def _value(name: str) -> str:
    """Return a configured value, treating untouched example placeholders as empty."""
    raw = _raw(name)
    lowered = raw.lower()
    if not raw:
        return ""
    if (
        lowered.startswith("your-")
        or "your-project" in lowered
        or "your-region" in lowered
        or lowered.startswith("https://your-")
    ):
        return ""
    return raw


def _choice(name: str, default: str, allowed: set[str]) -> str:
    raw = _raw(name).lower()
    if not raw:
        return default
    if raw not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of {allowed_list}, got {raw!r}")
    return raw


@dataclass(frozen=True)
class Settings:
    run_mode: RunMode
    input_mode: InputMode
    translation_mode: TranslationMode
    broadcast_mode: BroadcastMode
    source_language: str
    audio_file: str
    text_file: str
    azure_speech_key: str
    azure_speech_region: str
    azure_speech_endpoint: str
    azure_translator_key: str
    azure_translator_region: str
    azure_translator_endpoint: str
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str
    warnings: tuple[str, ...]

    def browser_config(self) -> dict[str, str]:
        """Public page settings. The service-role key is never included."""
        transport: BroadcastMode = self.broadcast_mode
        if transport == "local":
            return {
                "transport": "local",
                "supabaseUrl": "",
                "supabaseAnonKey": "",
                "runMode": self.run_mode,
                "translationMode": self.translation_mode,
            }
        if transport == "supabase":
            return {
                "transport": "supabase",
                "supabaseUrl": self.supabase_url,
                "supabaseAnonKey": self.supabase_anon_key,
                "runMode": self.run_mode,
                "translationMode": self.translation_mode,
            }
        assert_never(transport)


_settings: Settings | None = None


def get_settings() -> Settings:
    if _settings is None:
        return load_settings()
    return _settings


def load_settings() -> Settings:
    global _settings
    load_dotenv(ENV_PATH, override=False)

    speech_key = _value("AZURE_SPEECH_KEY")
    speech_region = _value("AZURE_SPEECH_REGION")
    translator_key = _value("AZURE_TRANSLATOR_KEY")
    translator_region = _value("AZURE_TRANSLATOR_REGION")
    supabase_url = _value("SUPABASE_URL")
    supabase_service_key = _value("SUPABASE_SERVICE_KEY")

    required_for_live = {
        "AZURE_SPEECH_KEY": speech_key,
        "AZURE_SPEECH_REGION": speech_region,
        "AZURE_TRANSLATOR_KEY": translator_key,
        "AZURE_TRANSLATOR_REGION": translator_region,
        "SUPABASE_URL": supabase_url,
        "SUPABASE_SERVICE_KEY": supabase_service_key,
    }
    missing = [name for name, value in required_for_live.items() if not value]
    warnings: list[str] = []

    explicit = _raw("RUN_MODE").lower()
    if explicit and explicit not in {"demo", "live"}:
        raise ValueError("RUN_MODE must be demo or live, got " + repr(explicit))
    if explicit == "live":
        run_mode: RunMode = "live"
    elif explicit == "demo":
        run_mode = "demo"
    elif not missing:
        run_mode = "live"
    else:
        run_mode = "demo"
        if any(required_for_live.values()):
            warnings.append(
                "Staying in demo mode because these are empty or still placeholders: "
                + ", ".join(missing)
                + ". Set RUN_MODE=live after filling them in."
            )
        else:
            warnings.append(
                "No credentials found. Demo mode feeds English text through mock "
                "translation and plays a short tone in the browser."
            )

    input_default = "text" if run_mode == "demo" else "microphone"
    translation_default = "mock" if run_mode == "demo" else "azure"
    broadcast_default = "local" if run_mode == "demo" else "supabase"

    input_mode = cast(InputMode, _choice("INPUT_MODE", input_default, {"text", "microphone", "file"}))
    translation_mode = cast(
        TranslationMode, _choice("TRANSLATION_MODE", translation_default, {"mock", "azure"})
    )
    broadcast_mode = cast(
        BroadcastMode, _choice("BROADCAST_MODE", broadcast_default, {"local", "supabase"})
    )

    anon_key = _value("SUPABASE_ANON_KEY")
    if broadcast_mode == "supabase" and not anon_key:
        warnings.append(
            "SUPABASE_ANON_KEY is empty. The laptop can still broadcast, but "
            "output.html cannot subscribe until the anon (or publishable) key is set."
        )

    source_language = _raw("SOURCE_LANGUAGE") or "en-US"
    endpoint = _value("AZURE_TRANSLATOR_ENDPOINT") or "https://api.cognitive.microsofttranslator.com"

    _settings = Settings(
        run_mode=run_mode,
        input_mode=input_mode,
        translation_mode=translation_mode,
        broadcast_mode=broadcast_mode,
        source_language=source_language,
        audio_file=_raw("AUDIO_FILE"),
        text_file=_raw("TEXT_FILE"),
        azure_speech_key=speech_key,
        azure_speech_region=speech_region,
        azure_speech_endpoint=_value("AZURE_SPEECH_ENDPOINT"),
        azure_translator_key=translator_key,
        azure_translator_region=translator_region,
        azure_translator_endpoint=endpoint,
        supabase_url=supabase_url,
        supabase_service_key=supabase_service_key,
        supabase_anon_key=anon_key,
        warnings=tuple(warnings),
    )
    return _settings


def configuration_errors(settings: Settings) -> list[str]:
    """Problems that make an explicitly live service fail closed."""
    if settings.run_mode != "live":
        return []
    errors: list[str] = []
    needs_speech = settings.input_mode in {"microphone", "file"} or settings.translation_mode == "azure"
    if needs_speech and (not settings.azure_speech_key or not settings.azure_speech_region):
        if settings.azure_speech_endpoint and settings.azure_speech_key:
            pass
        else:
            errors.append("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION (or AZURE_SPEECH_ENDPOINT)")
    if settings.input_mode == "file":
        if not settings.audio_file:
            errors.append("AUDIO_FILE pointing at a PCM WAV")
        elif not Path(settings.audio_file).is_file():
            errors.append(f"AUDIO_FILE not found: {settings.audio_file}")
    if settings.translation_mode == "azure":
        if not settings.azure_translator_key or not settings.azure_translator_region:
            errors.append("AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION")
    if settings.broadcast_mode == "supabase":
        if not settings.supabase_url or not settings.supabase_service_key:
            errors.append("SUPABASE_URL and SUPABASE_SERVICE_KEY (service role or sb_secret key, backend only)")
    return errors
