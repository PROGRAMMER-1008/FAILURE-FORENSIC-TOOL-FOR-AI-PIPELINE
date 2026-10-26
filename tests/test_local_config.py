import pytest

from ffv2.api import create_app
from ffv2.local import child_environment, local_settings
from ffv2.settings import Settings
from tests.test_api import request
from ffv2 import local


def test_explicit_dotenv_loading_and_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("FF_PROVIDER", raising=False)
    monkeypatch.delenv("FF_GROQ_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "FF_PROVIDER=groq\nFF_GROQ_API_KEY=unit-test-placeholder\nFF_PRODUCER_MODEL=test-model\n",
        encoding="utf-8",
    )
    settings = local_settings(path)
    assert settings.provider == "groq"
    assert settings.ai_ready
    assert "unit-test-placeholder" not in repr(settings)
    assert child_environment(settings)["FF_GROQ_API_KEY"] == "unit-test-placeholder"
    monkeypatch.setenv("FF_PROVIDER", "fake")
    assert local_settings(path).provider == "fake"


def test_default_settings_never_implicitly_load_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("FF_PROVIDER", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("FF_PROVIDER=groq", encoding="utf-8")
    assert Settings().provider == "fake"
    assert not Settings(provider="groq", groq_api_key="   ").ai_ready


def test_launcher_missing_and_invalid_config_are_sanitized(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(local, "ROOT", tmp_path)
    assert local.main() == 1
    assert "Missing .env" in capsys.readouterr().out
    monkeypatch.delenv("FF_DEADLINE_SECONDS", raising=False)
    (tmp_path / ".env").write_text("FF_DEADLINE_SECONDS=private-test-value", encoding="utf-8")
    assert local.main() == 1
    output = capsys.readouterr().out
    assert "Invalid local configuration" in output
    assert "private-test-value" not in output


@pytest.mark.enable_socket
def test_setup_status_is_safe_and_missing_key_blocks_submissions(store):
    app = create_app(Settings(provider="groq", groq_api_key=""), store)
    status = request(app, "GET", "/api/v1/config").json()
    assert status["ai_ready"] is False
    assert status["credential_status"] == "missing"
    body = {"text": "Invented document", "idempotency_key": "missing-key"}
    assert request(app, "POST", "/api/v1/runs", json=body).status_code == 503
    assert request(app, "POST", "/api/v1/uploads", content=b"sample").status_code == 503
    app = create_app(Settings(provider="groq", groq_api_key="unit-test-placeholder"), store)
    response = request(app, "GET", "/api/v1/config")
    assert response.json()["credential_status"] == "present_not_verified"
    assert "unit-test-placeholder" not in response.text
    assert "groq_api_key" not in response.text
