"""
STEP: Classification

Takes the raw document (and optionally what extraction found) and
classifies the document type: contract, invoice, report, or
correspondence.

Note: this step ONLY takes RawDocument as input, not the extraction
output. This is a deliberate design choice - see the note at the
bottom of this file.
"""

from pipeline.models import RawDocument, ClassificationResult, DocumentType
from pipeline.llm_client import call_llm_json


SYSTEM_PROMPT = """You are a document type classifier.
Classify the document into exactly one of: contract, invoice, report, correspondence.
If it genuinely doesn't fit any of these, use "unknown".

Respond ONLY with valid JSON in this exact shape:
{
  "document_type": "<contract|invoice|report|correspondence|unknown>",
  "confidence": <integer 1-5>,
  "reasoning": "<one short sentence explaining your choice>"
}
"""


def classify_document(doc: RawDocument) -> ClassificationResult:
    user_prompt = f"Classify this document:\n\n{doc.raw_text}"

    result = call_llm_json(SYSTEM_PROMPT, user_prompt)

    if not result.success or result.parsed_json is None:
        return ClassificationResult(
            doc_id=doc.doc_id,
            document_type=DocumentType.UNKNOWN,
            confidence=1,
            reasoning="Classification LLM call failed.",
        )

    try:
        doc_type_raw = result.parsed_json.get("document_type", "unknown").lower().strip()
        # Defensive mapping: if the model returns something not in our enum
        # (e.g. "letter" instead of "correspondence"), fall back to unknown
        # rather than crashing on Pydantic validation.
        try:
            doc_type = DocumentType(doc_type_raw)
        except ValueError:
            doc_type = DocumentType.UNKNOWN

        confidence = max(1, min(5, int(result.parsed_json.get("confidence", 1))))
        reasoning = result.parsed_json.get("reasoning", "")

        return ClassificationResult(
            doc_id=doc.doc_id,
            document_type=doc_type,
            confidence=confidence,
            reasoning=reasoning,
        )
    except Exception:
        return ClassificationResult(
            doc_id=doc.doc_id,
            document_type=DocumentType.UNKNOWN,
            confidence=1,
            reasoning="Failed to parse classification response.",
        )


# DESIGN NOTE - why classification doesn't take extraction's output:
#
# We deliberately keep this step reading from the RAW document rather
# than from the extraction step's output. Two reasons:
#
# 1. This is realistic: in the guide's 4-step design, classification and
#    extraction both read the raw intake, they don't chain off each other.
# 2. It gives us a clean way to demonstrate "propagation error" later -
#    if extraction hallucinates something and summarization (which DOES
#    read extraction's output) gets confused by it, that's a genuine
#    propagation failure. If classification were also reading extraction's
#    output, we'd have two propagation paths tangled together, making
#    root-cause analysis murkier for a portfolio demo.
