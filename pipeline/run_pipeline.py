"""
The full pipeline, wired together WITHOUT tracing yet.

We're deliberately building this "untraced" version first so you can
see and test the plain pipeline logic in isolation. In the next file,
we wrap this same logic with spans/tracing - keeping this version
around also makes it obvious exactly what the tracing layer ADDS,
rather than tracing being tangled into the core logic from the start.
"""

from pipeline.models import RawDocument, PipelineOutput
from pipeline.step_extraction import extract_entities
from pipeline.step_classification import classify_document
from pipeline.step_summarization import summarize_document


def run_pipeline(doc_id: str, raw_text: str) -> PipelineOutput:
    """Runs a document through all 4 steps (intake -> extract -> classify -> summarize)."""
    doc = RawDocument(doc_id=doc_id, raw_text=raw_text)

    extraction = extract_entities(doc)
    classification = classify_document(doc)
    summary = summarize_document(doc, extraction, classification)

    return PipelineOutput(
        doc_id=doc_id,
        raw_document=doc,
        extraction=extraction,
        classification=classification,
        summary=summary,
    )
