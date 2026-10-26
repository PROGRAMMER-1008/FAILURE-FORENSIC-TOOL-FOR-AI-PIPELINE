import json

import httpx
import pytest

from ffv2.providers import GroqProvider, configured_provider, execute
from ffv2.settings import Settings


def test_groq_request_and_contract(monkeypatch):
    settings = Settings(
        provider="groq",
        groq_api_key="test-only-placeholder",
        producer_model="test-producer",
        judge_model="test-judge",
    )
    original = httpx.Client
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only-placeholder"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"entities":[],"confidence":5}'}}],
                "usage": {"completion_tokens": 12},
            },
        )

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)
    )
    result = execute(configured_provider(settings), "extract", {"document": "Example"})
    assert result.status == "succeeded"
    assert result.tokens == 12
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert configured_provider(settings, judge=True).model == "test-judge"
    assert "test-only-placeholder" not in repr(settings)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_groq_errors_do_not_expose_response_or_key(monkeypatch, status):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, text="private-error")
            ),
            **kwargs,
        ),
    )
    result = execute(GroqProvider(Settings(groq_api_key="test-only-placeholder")), "extract", {})
    assert result.error == "provider_error"
    assert "private-error" not in result.model_dump_json()
    assert "test-only-placeholder" not in result.model_dump_json()


def test_missing_key_fails_without_network():
    result = execute(GroqProvider(Settings(groq_api_key="")), "extract", {})
    assert result.error == "provider_error"
