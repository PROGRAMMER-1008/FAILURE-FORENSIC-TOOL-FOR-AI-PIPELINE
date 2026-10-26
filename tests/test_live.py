"""One-call opt-in smoke test. Never part of default deterministic verification."""

import os
import pytest
from ffv2.providers import OllamaProvider, execute
from ffv2.settings import Settings
from ffv2.worker import SYNTHETIC_SOURCE


@pytest.mark.live
@pytest.mark.enable_socket
def test_live_ollama_schema_smoke():
    if os.environ.get("FF_LIVE_TEST") != "1":
        pytest.skip(
            "Live model not enabled; set FF_LIVE_TEST=1 with an installed model (one call, 30s deadline)"
        )
    settings = Settings(provider="ollama", deadline_seconds=30)
    result = execute(OllamaProvider(settings), "extract", {"document": SYNTHETIC_SOURCE})
    assert result.model == settings.producer_model
    assert result.status == "succeeded", result.error
