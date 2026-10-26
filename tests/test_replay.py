from ffv2.experiments import compare, experiment, ExperimentRequest
from ffv2.models import ReviewInput, Run
from ffv2.replay import replay, ReplayRequest
from ffv2.settings import Settings
from ffv2.worker import SYNTHETIC_SOURCE, run_one


def test_intervention_only_reruns_descendants_and_scores_gold(store):
    original = store.enqueue(
        Run(source=SYNTHETIC_SOURCE, source_hash="synthetic", config={"injected": True}), "original"
    )
    run_one(store, Settings())
    original = store.get(original.id)
    store.review(
        original.id,
        ReviewInput(
            idempotency_key="review",
            reviewer="test",
            revision=original.revision,
            target_finding_revision=1,
            verdict="correct",
            origins=["extract"],
            expected_output={"summarize": {"summary": "Synthetic invoice total: 814 EUR"}},
        ),
    )
    request = ReplayRequest(
        idempotency_key="replay",
        mode="reexecute",
        description="Known human correction",
        step_id="extract",
        corrected_output={
            "entities": [{"name": "Total", "value": "814 EUR", "entity_type": "amount"}],
            "confidence": 5,
        },
    )
    child = replay(store, original, request)
    run_one(store, Settings())
    child = store.get(child.id)
    comparison = compare(store, child)
    assert comparison["score"]["original_pass"] is False
    assert comparison["score"]["replay_pass"] is True
    assert comparison["changed_steps"] == ["extract", "summarize"]
    assert store.get(original.id).attempts[0].result.output["entities"][0]["value"] == "999 EUR"
    assert len(child.attempts) == 3


def test_fixture_experiment_is_labeled_and_idempotent(store):
    request = ExperimentRequest(mode="synthetic", idempotency_key="experiment")
    first = experiment(store, request)
    assert first["report"]["execution_mode"] == "synthetic_injected_mechanics_only"
    assert experiment(store, request) == first
