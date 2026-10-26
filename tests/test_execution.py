import pytest
from ffv2.providers import FakeProvider, execute


@pytest.mark.parametrize(
    "response,error",
    [
        (TimeoutError(), "timeout"),
        (ConnectionError(), "connection"),
        ("not JSON", "invalid_json"),
        ('{"entities": [], "confidence": 9}', "invalid_schema"),
        ('{"entities": [], "confidence": "5"}', "invalid_schema"),
        ("{}", "invalid_schema"),
    ],
)
def test_failures_are_not_empty_success(response, error):
    result = execute(FakeProvider({"extract": response}), "extract", {})
    assert result.status == "failed"
    assert result.error == error
    assert result.output is None


def test_literal_response_and_output_distinct():
    raw = '{ "entities": [], "confidence": 1 }'
    result = execute(FakeProvider({"extract": raw}), "extract", {})
    assert result.status == "succeeded"
    assert result.raw_response == raw
    assert result.output == {"entities": [], "confidence": 1}


def test_context_overflow():
    assert (
        execute(FakeProvider(), "extract", {"document": "a" * 100}, 20).error == "context_overflow"
    )
