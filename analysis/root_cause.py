"""
Backward root-cause analysis.

THE CORE IDEA (see our earlier walkthrough - this is the "rewind the
tape starting from the end" logic):
Given a trace that produced a bad final output, walk backward through
the spans (summarization -> classification -> extraction). At each
span, ask "does this look like a genuine problem?" using the evidence
we have: judge_score, self-reported confidence, and whether they
disagree. The FIRST span (walking backward) that looks like a real
problem is our root cause candidate - we stop there rather than
flagging every upstream span too, because usually only one step is
where things actually went wrong; everything after it is often just
a downstream victim (a "propagation error", see the taxonomy below).

WHY WE USE MULTIPLE SIGNALS, NOT JUST ONE:
We already have concrete evidence from real runs that:
  - self-confidence alone is unreliable (same document scored 4 vs 5
    on different runs)
  - the judge can articulate a real problem in its reasoning text
    without lowering its numeric score to match
So no single number is trustworthy alone. We combine signals and,
critically, we always surface the actual judge reasoning text to a
human - the number is a pointer to look closer, not a verdict.
"""

from enum import Enum
from pydantic import BaseModel

from pipeline.models import Trace, Span


class FailureCategory(str, Enum):
    """
    The taxonomy from the original project design, in plain terms:
      EXTRACTION_HALLUCINATION - invented an entity not in the source
      MISCLASSIFICATION        - wrong document type
      PROPAGATION_ERROR        - this step was fine GIVEN its input,
                                  but an earlier step handed it something
                                  bad and the problem carried forward
      PROMPT_FAILURE           - model ignored its instructions
      CONTEXT_LOSS             - something important silently disappeared
      PLACEHOLDER_AS_DATA      - our own addition, discovered empirically:
                                  treating "TBD"/"unknown" as real data
      UNCLEAR                  - evidence doesn't clearly point to one category
    """
    EXTRACTION_HALLUCINATION = "extraction_hallucination"
    MISCLASSIFICATION = "misclassification"
    PROPAGATION_ERROR = "propagation_error"
    PROMPT_FAILURE = "prompt_failure"
    CONTEXT_LOSS = "context_loss"
    PLACEHOLDER_AS_DATA = "placeholder_as_data"
    UNCLEAR = "unclear"


class RootCauseFinding(BaseModel):
    """The output of backward analysis on one trace."""
    trace_id: str
    root_cause_step: str | None  # None if no clear culprit found
    category: FailureCategory
    evidence: str  # the specific reasoning that points to this being the cause
    confidence_in_diagnosis: str  # "high" | "medium" | "low" - how sure WE are about this diagnosis
    downstream_steps_affected: list[str]  # steps after the root cause, likely just propagating it


# A span is a "suspect" if either signal looks bad, or they disagree a lot.
JUDGE_SCORE_SUSPECT_THRESHOLD = 3  # judge_score at or below this = suspicious
DISAGREEMENT_THRESHOLD = 2  # |confidence - judge_score| at or above this = suspicious


def _is_suspect(span: Span) -> bool:
    """Does this span look like a plausible culprit, based on available evidence?"""
    if span.judge_score is None:
        return False  # no judge data - we can't assess this span, don't guess
    if span.judge_score <= JUDGE_SCORE_SUSPECT_THRESHOLD:
        return True
    if abs(span.confidence - span.judge_score) >= DISAGREEMENT_THRESHOLD:
        return True
    return False


def _categorize(span: Span, earlier_steps_also_suspect: bool) -> FailureCategory:
    """
    Best-effort categorization using keyword signals in the judge's own
    reasoning text. This is intentionally simple (string matching, not
    another LLM call) - see the note at the bottom of this file for why.

    `earlier_steps_also_suspect` tells us whether any step BEFORE this
    one (in forward pipeline order) was also flagged as suspect. This is
    what actually distinguishes "this step invented something on its own"
    from "propagation error" - propagation specifically means an upstream
    step was ALSO bad, and this step just carried that problem forward.
    If nothing upstream was flagged, this step's invented content is its
    own original mistake, not inherited.
    """
    reasoning_lower = (span.judge_reasoning or "").lower()

    if "placeholder-as-data" in reasoning_lower or ("tbd" in reasoning_lower and "placeholder" in reasoning_lower):
        return FailureCategory.PLACEHOLDER_AS_DATA
    if "invented" in reasoning_lower or "hallucinat" in reasoning_lower or "not explicitly stated" in reasoning_lower:
        if earlier_steps_also_suspect:
            return FailureCategory.PROPAGATION_ERROR
        if span.step_name == "extraction":
            return FailureCategory.EXTRACTION_HALLUCINATION
        return FailureCategory.PROMPT_FAILURE  # this step invented content on its own, unprompted by upstream issues
    if span.step_name == "classification" and ("wrong" in reasoning_lower or "incorrect" in reasoning_lower):
        return FailureCategory.MISCLASSIFICATION
    if "missing" in reasoning_lower or "omit" in reasoning_lower or "dropped" in reasoning_lower:
        return FailureCategory.CONTEXT_LOSS
    if "ignore" in reasoning_lower or "instruction" in reasoning_lower:
        return FailureCategory.PROMPT_FAILURE

    return FailureCategory.UNCLEAR


def analyze_trace(trace: Trace) -> RootCauseFinding:
    """
    Walks a trace's spans BACKWARD (last step first) looking for the
    first suspect span. Everything after that span (in forward order)
    is treated as likely-downstream / propagation-affected.
    """
    spans_reversed = list(reversed(trace.spans))  # summarization, classification, extraction

    root_cause_span = None
    for span in spans_reversed:
        if _is_suspect(span):
            root_cause_span = span
            break  # stop at the FIRST suspect found walking backward

    if root_cause_span is None:
        return RootCauseFinding(
            trace_id=trace.trace_id,
            root_cause_step=None,
            category=FailureCategory.UNCLEAR,
            evidence="No span showed clear evidence of a problem (no low judge scores or major self/judge disagreement).",
            confidence_in_diagnosis="low",
            downstream_steps_affected=[],
        )

    # Figure out which steps come AFTER the root cause in forward order -
    # those are the ones most likely just propagating the upstream problem.
    forward_order = [s.step_name for s in trace.spans]
    root_idx = forward_order.index(root_cause_span.step_name)
    downstream = forward_order[root_idx + 1:]

    is_first_step = root_cause_span.step_name == "extraction"

    # Check whether any step BEFORE the root cause (in forward pipeline
    # order) was also flagged as suspect - this is what distinguishes a
    # genuine propagation error from this step's own original mistake.
    root_idx_forward = forward_order.index(root_cause_span.step_name)
    steps_before = trace.spans[:root_idx_forward]
    earlier_steps_also_suspect = any(_is_suspect(s) for s in steps_before)

    category = _categorize(root_cause_span, earlier_steps_also_suspect)

    # How confident are WE (the analyzer) in this diagnosis? Simple heuristic:
    # a low judge_score is stronger evidence than disagreement alone, and
    # having explicit reasoning text to point to is stronger than a bare number.
    if root_cause_span.judge_score is not None and root_cause_span.judge_score <= 2 and root_cause_span.judge_reasoning:
        diag_confidence = "high"
    elif root_cause_span.judge_reasoning:
        diag_confidence = "medium"
    else:
        diag_confidence = "low"

    return RootCauseFinding(
        trace_id=trace.trace_id,
        root_cause_step=root_cause_span.step_name,
        category=category,
        evidence=root_cause_span.judge_reasoning or "(no reasoning text available)",
        confidence_in_diagnosis=diag_confidence,
        downstream_steps_affected=downstream,
    )


# NOTE on why _categorize uses keyword matching instead of another LLM call:
# We could send the judge's reasoning to yet another LLM prompt asking
# "which category does this fall into?" - and that might be more robust.
# We chose simple keyword matching for v1 because: (1) it's instant and
# free, (2) it's fully deterministic and debuggable - you can read the
# exact rule that fired, (3) our judge prompt was specifically written
# to name failure types explicitly (e.g. "placeholder-as-data error"),
# so keyword matching against OUR OWN prompt's vocabulary is more
# reliable than it would be against free-form text. A documented v2
# improvement, not a hidden shortcut.