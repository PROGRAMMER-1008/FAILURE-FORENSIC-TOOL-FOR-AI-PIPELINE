"""
STEP: Extraction

Takes raw document text, asks the LLM to pull out key entities
(names, dates, amounts, organizations), and returns a typed
ExtractionResult.

WHY THIS STEP IS ISOLATED:
Notice this function does exactly one job and has one clear
input/output. It doesn't know anything about classification or
summarization. This isolation is what lets the tracing layer
(which we build next) treat this as a single clean "span" - it
records what went in, what came out, and nothing else leaks in
between.
"""

from pipeline.models import RawDocument, ExtractionResult, ExtractedEntity
from pipeline.llm_client import call_llm_json


SYSTEM_PROMPT = """You are a precise document entity extractor.
Extract only entities that are EXPLICITLY present in the text.
Do NOT infer, guess, or add entities that aren't clearly stated.
If the document has no clear entities of a type, don't include placeholder entities.

Respond ONLY with valid JSON in this exact shape:
{
  "entities": [
    {"name": "<the actual value found>", "value": "<same value or normalized form>", "entity_type": "<person|date|amount|organization|other>"}
  ],
  "confidence": <integer 1-5, how confident you are these extractions are complete and correct>
}
"""


def extract_entities(doc: RawDocument) -> ExtractionResult:
    """
    Runs entity extraction on a raw document.

    If the LLM call fails or returns something that doesn't match
    our expected schema, we return a low-confidence empty result
    rather than crashing - the tracing layer will flag this as a
    failed/degraded span, which is itself useful information.
    """
    user_prompt = f"Extract entities from this document:\n\n{doc.raw_text}"

    result = call_llm_json(SYSTEM_PROMPT, user_prompt)

    if not result.success or result.parsed_json is None:
        # LLM call itself failed - return an empty, zero-confidence result
        # rather than letting the whole pipeline crash on one bad document.
        return ExtractionResult(doc_id=doc.doc_id, entities=[], confidence=1)

    try:
        entities = [
            ExtractedEntity(**e) for e in result.parsed_json.get("entities", [])
        ]
        confidence = result.parsed_json.get("confidence", 1)
        # Defensive clamp - a local model might return an out-of-range number
        # despite instructions. Better to clamp than crash on Pydantic validation.
        confidence = max(1, min(5, int(confidence)))

        return ExtractionResult(
            doc_id=doc.doc_id,
            entities=entities,
            confidence=confidence,
        )
    except Exception:
        # The JSON parsed, but didn't match our expected shape
        # (e.g. model put entities as strings instead of objects).
        # Same fallback: empty, low-confidence, pipeline keeps moving.
        return ExtractionResult(doc_id=doc.doc_id, entities=[], confidence=1)
