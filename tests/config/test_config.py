"""Tests for felix.config."""

import pytest

from felix.config import load_settings


def test_load_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("SF_CLIENT_ID", "client-id")
    monkeypatch.setenv("SF_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv(
        "SF_INSTANCE_URL",
        "https://example.my.salesforce.com/",
    )
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "cache.sqlite"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))

    settings = load_settings()

    assert settings.sf_client_id == "client-id"
    assert settings.sf_client_secret == "client-secret"
    assert settings.sf_instance_url == "https://example.my.salesforce.com"
    assert settings.sf_api_version == "59.0"
    assert settings.cache_path == tmp_path / "cache.sqlite"
    assert settings.output_dir == tmp_path / "out"


def test_missing_credential_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ("SF_CLIENT_ID", "SF_CLIENT_SECRET", "SF_INSTANCE_URL"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValueError, match="SF_CLIENT_ID") as exc_info:
        load_settings()

    message = str(exc_info.value)
    assert "SF_CLIENT_SECRET" in message
    assert "SF_INSTANCE_URL" in message


def test_rejects_setup_ui_host(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SF_CLIENT_ID", "client-id")
    monkeypatch.setenv("SF_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv(
        "SF_INSTANCE_URL",
        "https://org.salesforce-setup.com/lightning/setup/home",
    )

    with pytest.raises(ValueError, match="Setup UI"):
        load_settings()
