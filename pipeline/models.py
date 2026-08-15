"""
Core data models for the document processing pipeline.

WHY THIS FILE MATTERS:
Every pipeline step takes a typed input and returns a typed output.
This is what makes tracing meaningful - if steps passed around loose
dicts or strings, we couldn't reliably capture clean "before/after"
snapshots for each span. Pydantic enforces the shape of data at
every boundary, so when something looks wrong in a trace, we know
it's a real problem and not just a typo in a dict key.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class DocumentType(str, Enum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    REPORT = "report"
    CORRESPONDENCE = "correspondence"
    UNKNOWN = "unknown"


# ---------- Step 1: Intake ----------

class RawDocument(BaseModel):
    """What goes INTO the pipeline."""
    doc_id: str
    raw_text: str


# ---------- Step 2: Extraction ----------

class ExtractedEntity(BaseModel):
    name: str
    value: str
    entity_type: str  # e.g. "person", "date", "amount", "org"


class ExtractionResult(BaseModel):
    doc_id: str
    entities: list[ExtractedEntity]
    confidence: int = Field(ge=1, le=5, description="Model's self-reported confidence 1-5")


# ---------- Step 3: Classification ----------

class ClassificationResult(BaseModel):
    doc_id: str
    document_type: DocumentType
    confidence: int = Field(ge=1, le=5)
    reasoning: str  # short explanation of why this type was chosen


# ---------- Step 4: Summarization ----------

class SummaryResult(BaseModel):
    doc_id: str
    summary: str
    confidence: int = Field(ge=1, le=5)


# ---------- Final pipeline output ----------

class PipelineOutput(BaseModel):
    doc_id: str
    raw_document: RawDocument
    extraction: ExtractionResult
    classification: ClassificationResult
    summary: SummaryResult


# ---------- Tracing ----------

class TraceStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DEGRADED = "degraded"  # ran, but something looked off (e.g. very low confidence)


class Span(BaseModel):
    """
    One recorded step. This is the 'camera footage' for a single worker
    at their desk: what they were handed, what they produced, how
    confident they said they were, and how long it took.
    """
    step_name: str  # "extraction", "classification", "summarization"
    input_summary: str  # human-readable snapshot of what went in
    output_summary: str  # human-readable snapshot of what came out
    confidence: int = Field(ge=1, le=5)  # the step's OWN self-reported confidence
    latency_seconds: float
    llm_raw_response: str  # the exact raw text the model returned - critical for forensics
    success: bool  # did the step complete without error (not the same as "was it correct")

    # Independent judge review - filled in AFTER the trace completes, by a
    # separate LLM call that never saw the step's own reasoning. See
    # analysis/judge.py for why this is kept separate from `confidence`.
    judge_score: int | None = Field(default=None, ge=1, le=5)
    judge_reasoning: str | None = None


class Trace(BaseModel):
    """
    The full recording of one document's journey through all 4 steps.
    This is what the backward root-cause analyzer will walk through.
    """
    trace_id: str
    doc_id: str
    spans: list[Span]
    final_output: PipelineOutput | None = None
    status: TraceStatus = TraceStatus.SUCCESS
    flagged_bad: bool = False  # set to True when a human flags this trace


# ---------- Feedback loop / growing eval dataset ----------

class ReviewVerdict(str, Enum):
    CONFIRMED = "confirmed"  # human agrees with the analyzer's diagnosis
    CORRECTED = "corrected"  # human disagreed and provided the right answer
    UNCLEAR = "unclear"      # human isn't confident enough to add this as ground truth


class EvalCase(BaseModel):
    """
    One permanent, human-verified test case, generated from a real
    pipeline failure. This is the 'flashcard' - a record of exactly
    what went wrong, confirmed or corrected by a human, that can be
    replayed later to check whether the pipeline still fails the
    same way after changes.
    """
    eval_case_id: str
    source_trace_id: str
    doc_id: str
    original_input_text: str
    failing_step: str
    bad_output: str
    correct_output: str          # what SHOULD have been produced - human-provided
    failure_category: str        # accepted or corrected category, as a plain string
    verdict: ReviewVerdict
    reviewer_notes: str = ""
    created_at: str = ""
