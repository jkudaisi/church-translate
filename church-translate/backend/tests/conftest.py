"""Keep tests in demo mode unless a test opts into something else."""

from __future__ import annotations

import pytest

from broadcast import local_hub
from config import load_settings

_ENV_KEYS = (
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
    "AZURE_SPEECH_ENDPOINT",
    "AZURE_TRANSLATOR_KEY",
    "AZURE_TRANSLATOR_REGION",
    "AZURE_TRANSLATOR_ENDPOINT",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_ANON_KEY",
    "RUN_MODE",
    "INPUT_MODE",
    "TRANSLATION_MODE",
    "BROADCAST_MODE",
    "AUDIO_FILE",
    "TEXT_FILE",
    "SOURCE_LANGUAGE",
)


@pytest.fixture(autouse=True)
def demo_env(monkeypatch: pytest.MonkeyPatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RUN_MODE", "demo")
    local_hub.reset()
    load_settings()
    yield
    local_hub.reset()
