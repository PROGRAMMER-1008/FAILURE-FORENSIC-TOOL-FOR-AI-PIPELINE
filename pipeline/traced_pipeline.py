"""
Traced pipeline: same 3 steps as run_pipeline.py, but every step is
wrapped with a Span that records what happened.

WHY A SEPARATE FILE INSTEAD OF EDITING run_pipeline.py:
Keeping the untraced version around makes it obvious exactly what
"tracing" adds on top of plain pipeline logic - it's not tangled
into the core steps themselves. In a real system you'd likely only
keep this traced version, but for learning purposes the separation
is useful.
"""

import time
import uuid

from pipeline.models import RawDocument, Trace, Span, TraceStatus
from pipeline.step_extraction import extract_entities
from pipeline.step_classification import classify_document
from pipeline.step_summarization import summarize_document


# A step is "degraded" if its self-reported confidence is at or below this.
# This is a heuristic threshold, not a hard rule - see the discussion in
# analysis/root_cause.py for why confidence is a "prime suspect" signal,
# not proof of an actual error.
LOW_CONFIDENCE_THRESHOLD = 2


def _truncate(text: str, max_len: int = 200) -> str:
    """
    Keeps UI-facing display text readable. IMPORTANT: this must NEVER be
    used for text that gets sent to the judge - truncating what the judge
    sees can silently hide real entities, making the judge wrongly flag
    genuine extractions as 'not present in the input'. See
    _full_entities_text() below for the untruncated version used in
    judge input.
    """
    text = text.strip()
    return text if len(text) <= max_len else text[:max_len] + "..."


def _full_entities_text(entities) -> str:
    """
    Full, untruncated, clearly-structured rendering of extracted
    entities - one per line, not a comma-joined blob. This is what
    the JUDGE sees (via judge.py reading output_summary... but we now
    also expose this separately, see judge_input_text on Span).
    Comma-joined single-line text is harder for a model to reliably
    cross-reference against source text than a clean per-line list,
    and truncating it (as the old _truncate() did at 200 chars) could
    silently drop real entities from what the judge even considers -
    causing exactly the kind of false 'invented content' accusation
    we saw on the invoice trace.
    """
    if not entities:
        return "(no entities extracted)"
    return "\n".join(f"- {e.entity_type}: {e.name}" for e in entities)


def run_traced_pipeline(doc_id: str, raw_text: str) -> Trace:
    """
    Runs the full pipeline while recording a Span for every step.
    Returns a complete Trace, ready to be saved/inspected/analyzed.
    """
    trace_id = str(uuid.uuid4())
    doc = RawDocument(doc_id=doc_id, raw_text=raw_text)
    spans: list[Span] = []
    overall_status = TraceStatus.SUCCESS

    # ---- Span 1: Extraction ----
    t0 = time.time()
    extraction = extract_entities(doc)
    latency = time.time() - t0

    full_entities_text = _full_entities_text(extraction.entities)
    spans.append(Span(
        step_name="extraction",
        input_summary=doc.raw_text,  # full text, not truncated - judge needs to see everything
        output_summary=full_entities_text,  # full untruncated list, not a truncated comma string
        confidence=extraction.confidence,
        latency_seconds=latency,
        llm_raw_response=full_entities_text,
        success=True,
    ))
    if extraction.confidence <= LOW_CONFIDENCE_THRESHOLD:
        overall_status = TraceStatus.DEGRADED

    # ---- Span 2: Classification ----
    t0 = time.time()
    classification = classify_document(doc)
    latency = time.time() - t0

    spans.append(Span(
        step_name="classification",
        input_summary=doc.raw_text,  # full text - same reasoning as extraction above
        output_summary=f"type={classification.document_type.value}\nreasoning={classification.reasoning}",
        confidence=classification.confidence,
        latency_seconds=latency,
        llm_raw_response=classification.reasoning,
        success=True,
    ))
    if classification.confidence <= LOW_CONFIDENCE_THRESHOLD:
        overall_status = TraceStatus.DEGRADED

    # ---- Span 3: Summarization ----
    t0 = time.time()
    summary = summarize_document(doc, extraction, classification)
    latency = time.time() - t0

    # Judge input for summarization includes BOTH the original document
    # AND the extracted entities - the judge needs the source text itself
    # to verify claims, not just our intermediate extraction (which could
    # itself be incomplete). This was a second real gap: the old version
    # only gave the judge the entities list, never the original document,
    # making it impossible for the judge to correctly verify claims like
    # "the invoice number is 15000001" against the actual source.
    summarization_judge_input = (
        f"ORIGINAL DOCUMENT:\n{doc.raw_text}\n\n"
        f"EXTRACTED ENTITIES (from an earlier step):\n{full_entities_text}\n\n"
        f"DOCUMENT TYPE: {classification.document_type.value}"
    )

    spans.append(Span(
        step_name="summarization",
        input_summary=summarization_judge_input,
        output_summary=summary.summary,
        confidence=summary.confidence,
        latency_seconds=latency,
        llm_raw_response=summary.summary,
        success=True,
    ))
    if summary.confidence <= LOW_CONFIDENCE_THRESHOLD:
        overall_status = TraceStatus.DEGRADED

    from pipeline.models import PipelineOutput
    final_output = PipelineOutput(
        doc_id=doc_id,
        raw_document=doc,
        extraction=extraction,
        classification=classification,
        summary=summary,
    )

    return Trace(
        trace_id=trace_id,
        doc_id=doc_id,
        spans=spans,
        final_output=final_output,
        status=overall_status,
    )


# NOTE on llm_raw_response:
# Right now each Span's llm_raw_response is reconstructed from the typed
# result (e.g. the entities we parsed), not the model's literal raw text.
# For a first working version this is fine - it's still faithful to what
# the step produced. A stronger v2 would have step_extraction.py etc.
# return the LLMCallResult.raw_response alongside the typed result, so
# spans capture the model's exact original words. Documented here as a
# known improvement rather than silently pretending this is the literal
# raw text - that distinction matters if you're asked about it in an
# interview.
