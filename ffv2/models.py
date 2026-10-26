from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return str(uuid4())


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Execution = Literal["queued", "running", "succeeded", "failed", "cancelled", "skipped"]
Quality = Literal["unassessed", "acceptable", "suspected_issue", "confirmed_issue", "inconclusive"]
ErrorKind = Literal[
    "timeout",
    "connection",
    "invalid_json",
    "invalid_schema",
    "cancelled",
    "context_overflow",
    "provider_error",
]


class Step(Model):
    id: str
    name: str
    dependencies: list[str]
    contract: str = "1"
    prompt_version: str = "1"


class PipelineVersion(Model):
    id: str = "document-v2.1"
    steps: list[Step] = Field(
        default_factory=lambda: [
            Step(id="extract", name="Extraction", dependencies=["document"]),
            Step(id="classify", name="Classification", dependencies=["document"]),
            Step(
                id="summarize",
                name="Summarization",
                dependencies=["document", "extract", "classify"],
            ),
        ]
    )

    @model_validator(mode="after")
    def valid_dag(self):
        seen = {"document"}
        for step in self.steps:
            if step.id in seen or not set(step.dependencies) <= seen:
                raise ValueError("Steps must have unique IDs and topological dependencies")
            seen.add(step.id)
        return self


class Entity(Model):
    name: str
    value: str
    entity_type: str


class Extraction(Model):
    entities: list[Entity]
    confidence: int = Field(strict=True, ge=1, le=5)


class Classification(Model):
    document_type: Literal["invoice", "contract", "report", "correspondence", "unknown"]
    confidence: int = Field(strict=True, ge=1, le=5)
    reasoning: str


class Summary(Model):
    summary: str
    confidence: int = Field(strict=True, ge=1, le=5)


CONTRACTS: dict[str, type[Model]] = {
    "extract": Extraction,
    "classify": Classification,
    "summarize": Summary,
}


class Envelope(Model):
    status: Execution
    output: dict[str, Any] | None = None
    raw_response: str = ""
    raw_redacted: bool = True
    error: ErrorKind | None = None
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)
    provider: str
    model: str
    elapsed_seconds: float = 0
    tokens: int | None = None


class Citation(Model):
    source_id: str = "document"
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str = Field(min_length=1)


class Issue(Model):
    category: Literal[
        "technical",
        "schema",
        "extraction",
        "misclassification",
        "omitted_context",
        "unsupported_claim",
        "placeholder",
        "propagation",
        "unclear",
    ]
    severity: Literal["low", "medium", "high"]
    field: str
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    inherited_from: list[str] = Field(default_factory=list)


class Judgment(Model):
    schema_version: int = 1
    evaluator_version: str = "source-faithfulness-1"
    model: str
    status: Literal["assessed", "unavailable", "invalid"] = "assessed"
    assessment: Literal["acceptable", "issue", "inconclusive"]
    source_correct: bool | None = None
    input_faithful: bool | None = None
    issues: list[Issue] = Field(default_factory=list)
    uncertainty: str


class Attempt(Model):
    id: str = Field(default_factory=uid)
    step_id: str
    dependencies: list[str]
    number: int = 1
    started_at: str = Field(default_factory=now)
    ended_at: str | None = None
    inputs: dict[str, Any]
    result: Envelope
    judgment: Judgment | None = None


class Finding(Model):
    revision: int = 1
    analyzer_version: str = "graph-evidence-1"
    origins: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    potentially_affected: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    abstention_reason: str | None = None
    label: str = "Diagnosis hypothesis; not established causality"


class Run(Model):
    schema_version: int = 2
    id: str = Field(default_factory=uid)
    source: str
    source_hash: str
    created_at: str | None = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    status: Execution = "queued"
    quality: Quality = "unassessed"
    pipeline: PipelineVersion = Field(default_factory=PipelineVersion)
    config: dict[str, Any] = Field(default_factory=dict)
    attempts: list[Attempt] = Field(default_factory=list)
    finding: Finding | None = None
    parent_id: str | None = None
    retention: str = "redacted; local retention until explicit deletion"
    revision: int = 0


class ReviewInput(Model):
    idempotency_key: str = Field(min_length=1, max_length=100)
    reviewer: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=0)
    target_finding_revision: int = Field(ge=1)
    verdict: Literal["confirm", "correct", "unclear", "no_issue", "missed_failure"]
    origins: list[str] = Field(default_factory=list)
    category: str = "unclear"
    notes: str = Field(default="", max_length=4000)
    expected_output: dict[str, Any] | None = None
