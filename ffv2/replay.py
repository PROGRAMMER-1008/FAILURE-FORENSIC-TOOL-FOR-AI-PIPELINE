from typing import Literal
from pydantic import Field
from ffv2.diagnosis import descendants
from ffv2.models import CONTRACTS, Model, Run, uid
from ffv2.store import Conflict, Store


class ReplayRequest(Model):
    idempotency_key: str = Field(min_length=1, max_length=100)
    mode: Literal["recorded", "reexecute"]
    description: str = Field(min_length=1, max_length=1000)
    step_id: str | None = None
    corrected_output: dict | None = None


def replay(store: Store, original: Run, request: ReplayRequest) -> Run:
    if original.status not in {"succeeded", "failed", "cancelled"}:
        raise Conflict("Wait for a terminal run")
    if request.mode == "recorded":
        return original  # Explicit artifact viewing; no new inference or fake progress.
    if (request.step_id is None) != (request.corrected_output is None):
        raise Conflict("Intervention requires both a step ID and structured corrected output")
    run = Run(
        source=original.source,
        source_hash=original.source_hash,
        pipeline=original.pipeline,
        parent_id=original.id,
        config={
            **original.config,
            "replay": request.model_dump(),
            "injected": original.config.get("injected", False)
            if request.step_id is None
            else False,
        },
    )
    if request.step_id:
        if request.step_id not in CONTRACTS:
            raise Conflict("Unsupported intervention step")
        corrected = (
            CONTRACTS[request.step_id]
            .model_validate(request.corrected_output)
            .model_dump(mode="json")
        )
        affected = descendants(original, request.step_id)
        for attempt in original.attempts:
            if attempt.step_id in affected or attempt.result.status != "succeeded":
                continue
            copied = attempt.model_copy(deep=True)
            copied.id = uid()
            if copied.step_id == request.step_id:
                copied.result.output = corrected
                copied.result.raw_response = ""
                copied.result.provider = "human_intervention"
                copied.result.model = "not-inference"
                copied.result.elapsed_seconds = 0
                copied.judgment = None
            run.attempts.append(copied)
    return store.enqueue(run, request.idempotency_key)
