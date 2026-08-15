"""
STEP: Summarization

This is the ONLY step that reads the outputs of earlier steps
(extraction + classification) rather than just the raw document.
That's intentional - this is where a mistake made upstream (say,
a hallucinated entity in extraction) can propagate forward into
the final output. When we build root-cause analysis, this is the
step most likely to reveal "propagation errors" vs. its own
original mistakes.
"""

from pipeline.models import RawDocument, ExtractionResult, ClassificationResult, SummaryResult
from pipeline.llm_client import call_llm_json


SYSTEM_PROMPT = """You are a document summarizer. You will be given:
1. The original document text
2. A list of entities that were already extracted from it
3. The document's classified type

Write a short, structured summary (2-4 sentences) tailored to the document type.
Use the extracted entities where relevant, but you may also refer to the original
text directly. Do not invent information not present in the document or entities.

Respond ONLY with valid JSON in this exact shape:
{
  "summary": "<the summary text>",
  "confidence": <integer 1-5>
}
"""


def summarize_document(
    doc: RawDocument,
    extraction: ExtractionResult,
    classification: ClassificationResult,
) -> SummaryResult:
    entities_str = "\n".join(
        f"- {e.entity_type}: {e.name}" for e in extraction.entities
    ) or "(no entities were extracted)"

    user_prompt = f"""Original document:
{doc.raw_text}

Extracted entities:
{entities_str}

Document type: {classification.document_type.value}

Write the summary now."""

    result = call_llm_json(SYSTEM_PROMPT, user_prompt)

    if not result.success or result.parsed_json is None:
        return SummaryResult(
            doc_id=doc.doc_id,
            summary="",
            confidence=1,
        )

    try:
        summary_text = result.parsed_json.get("summary", "")
        confidence = max(1, min(5, int(result.parsed_json.get("confidence", 1))))

        return SummaryResult(
            doc_id=doc.doc_id,
            summary=summary_text,
            confidence=confidence,
        )
    except Exception:
        return SummaryResult(doc_id=doc.doc_id, summary="", confidence=1)
