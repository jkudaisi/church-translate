from __future__ import annotations

import pytest

from config import configuration_errors, load_settings


def test_empty_env_is_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_MODE", raising=False)
    settings = load_settings()
    assert settings.run_mode == "demo"
    assert settings.input_mode == "text"
    assert settings.translation_mode == "mock"
    assert settings.broadcast_mode == "local"
    assert configuration_errors(settings) == []
    browser = settings.browser_config()
    assert browser["transport"] == "local"
    assert browser["supabaseAnonKey"] == ""
    assert "supabase_service_key" not in browser


def test_placeholders_do_not_count_as_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_MODE", raising=False)
    monkeypatch.setenv("AZURE_SPEECH_KEY", "your-speech-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "your-speech-region")
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "your-translator-key")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "your-translator-region")
    monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "your-service-role-key")
    settings = load_settings()
    assert settings.run_mode == "demo"
    assert settings.azure_speech_key == ""
    assert settings.supabase_service_key == ""


def test_real_keys_default_to_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_MODE", raising=False)
    monkeypatch.setenv("AZURE_SPEECH_KEY", "speech-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "translator-key")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "eastus")
    monkeypatch.setenv("SUPABASE_URL", "https://abccompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role-secret")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public")
    settings = load_settings()
    assert settings.run_mode == "live"
    assert settings.input_mode == "microphone"
    assert settings.translation_mode == "azure"
    assert settings.broadcast_mode == "supabase"
    assert configuration_errors(settings) == []
    browser = settings.browser_config()
    assert browser["supabaseAnonKey"] == "anon-public"
    assert "service-role-secret" not in browser.values()


def test_live_mode_lists_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "live")
    settings = load_settings()
    errors = configuration_errors(settings)
    assert any("AZURE_SPEECH_KEY" in item for item in errors)
    assert any("AZURE_TRANSLATOR_KEY" in item for item in errors)
    assert any("SUPABASE_URL" in item for item in errors)


def test_invalid_run_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "sometimes")
    with pytest.raises(ValueError, match="RUN_MODE"):
        load_settings()
