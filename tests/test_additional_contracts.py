import pytest
from ffv2.models import Run, PipelineVersion, Step
from ffv2.providers import execute, FakeProvider
from ffv2.diagnosis import descendants


def test_empty_extraction_and_unknown_classification_are_valid():
    for step, raw in [
        ("extract", '{"entities":[],"confidence":1}'),
        (
            "classify",
            '{"document_type":"unknown","confidence":1,"reasoning":"Insufficient source"}',
        ),
    ]:
        assert execute(FakeProvider({step: raw}), step, {}).status == "succeeded"


def test_repeated_display_names_have_distinct_dependency_ids():
    run = Run(
        source="synthetic",
        source_hash="fixture",
        pipeline=PipelineVersion(
            id="repeat-1",
            steps=[
                Step(id="first", name="Repeated", dependencies=["document"]),
                Step(id="other", name="Repeated", dependencies=["document"]),
                Step(id="child", name="Repeated", dependencies=["first"]),
            ],
        ),
    )
    assert descendants(run, "first") == {"child"}
    assert descendants(run, "other") == set()


def test_enqueue_rollback_leaves_no_orphan_run(store, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Injected transactional failure")

    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(RuntimeError):
        store.enqueue(Run(source="synthetic", source_hash="fixture"), "rollback")
    assert store.list_runs() == []
