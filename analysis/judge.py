"""
LLM-as-judge: an independent quality check for each span.

WHY THIS IS SEPARATE FROM A STEP'S OWN self-reported confidence:
A step's confidence is the model grading its own work - a weak signal,
since the model has no real self-awareness. The judge is a DIFFERENT
LLM call that only sees (input, output) for one step - never the
step's own reasoning - and asks "is this output actually grounded in
and faithful to the input?" This is closer to how you'd want a human
reviewer to check work: fresh eyes, no access to the original
justification.

HONEST LIMITATION (documented, not hidden):
We're running the judge on the same local 8B model that produced the
original output. This is NOT the "strong model reviews weak model"
setup the original project guide assumes (e.g. GPT-4o judging a
cheaper model). Our judge can miss the same kinds of things the
original step missed, and - as we've already observed with
self-confidence being inconsistent between runs - its scores may
vary somewhat between runs too. It is still a meaningfully more
useful signal than self-confidence alone, because it's at least
looking at evidence rather than just asserting a feeling.
"""

from pipeline.llm_client import call_llm_json
from pipeline.models import Span

JUDGE_SYSTEM_PROMPT = """You are an independent quality reviewer for one step
of a document-processing pipeline. You did NOT produce this output - you are
reviewing someone else's work with fresh eyes.

You will be given:
1. What the step received as input
2. What the step produced as output

IMPORTANT - READ THE INPUT CAREFULLY FIRST: real-world documents are often
NOT plain prose. They may be invoices, forms, tables, address blocks, or
have ASCII-art formatting, box-drawing characters, aligned columns, or
unusual layout. Information presented in a table cell, form field, address
block, or aligned column IS just as "stated in the input" as information
in a full sentence - formatting or layout is NOT evidence that something
is missing, invented, or uncertain. Before making any claim that something
is "not present" or "invented", re-scan the ENTIRE input text yourself,
including any tables, headers, or structured sections, not just the
prose paragraphs. A very common and serious mistake is claiming a value
is invented when it is actually sitting in a table row, form field, or
address block in the input - check for this specifically before flagging
anything as invented.

Judge whether the output is a reasonable, well-grounded transformation of
the input. Check EACH of these specific failure types, in order, before
giving your score:

1. INVENTED CONTENT: Is there anything in the output that is NOT actually
   present ANYWHERE in the input, including tables, forms, and structured
   sections? Re-read the full input before answering this. If the value
   appears anywhere in the input, even in a table or form field, it is
   NOT invented.

2. PLACEHOLDER-AS-DATA (check this carefully, it is easy to miss): Does the
   output treat a placeholder, non-answer, or "to be determined" style
   phrase (e.g. "TBD", "N/A", "unknown", "pending", "to be confirmed") as if
   it were a real, concrete data value? For example, extracting "amount: TBD"
   is a placeholder-as-data error, because TBD means NO amount was actually
   stated - it should not be presented as an extracted value at all.

3. MISSING INFORMATION: Does the output omit something important that IS
   clearly present in the input?

4. CONTRADICTION: Does the output contradict what the input actually says?

5. OVER-CONFIDENT FRAMING: Does the output use more definite, narrative, or
   confident-sounding language than the input actually supports (e.g.
   turning a vague, unresolved situation into a description that reads as
   settled fact)? Note: restating a concrete fact that IS in the input
   (like an invoice number or total) in plain sentence form is NOT
   over-confident framing - it's just restating a fact. Over-confident
   framing means adding certainty about something that was actually
   AMBIGUOUS or UNSTATED in the input, not restating something that was
   clearly stated.

Go through checks 1-5 explicitly in your reasoning before scoring. If you
claim something is invented (check 1), you must be able to point to why
it does not appear anywhere in the input - if you cannot find that specific
justification, do not make the claim.
find a placeholder-as-data error (check 2), you MUST mention it by name in
your reasoning and it should meaningfully lower your score (3 or below).

Respond ONLY with valid JSON in this exact shape:
{
  "judge_score": <integer 1-5, where 5 = fully grounded and correct, 1 = seriously flawed>,
  "judge_reasoning": "<specific, concrete explanation referencing which check(s) above applied>"
}
"""


def judge_span(span: Span) -> Span:
    """
    Runs an independent judge review on a single span and returns a
    NEW Span with judge_score/judge_reasoning filled in.

    We return a new Span rather than mutating in place - keeping data
    transformations explicit (new object in, new object out) is the
    same discipline we used for the pipeline steps themselves, and it
    avoids subtle bugs where a caller assumes the original span is untouched.
    """
    user_prompt = f"""Step name: {span.step_name}

INPUT the step received:
{span.input_summary}

OUTPUT the step produced:
{span.output_summary}

Judge this now."""

    result = call_llm_json(JUDGE_SYSTEM_PROMPT, user_prompt)

    if not result.success or result.parsed_json is None:
        # Judge call itself failed - leave judge fields as None rather than
        # guessing. A None judge_score is meaningfully different from a
        # low score - it means "we don't know," not "this looks bad."
        return span.model_copy(update={
            "judge_score": None,
            "judge_reasoning": f"Judge call failed: {result.error}",
        })

    try:
        score = int(result.parsed_json.get("judge_score", 3))
        score = max(1, min(5, score))  # defensive clamp, same as elsewhere
        reasoning = result.parsed_json.get("judge_reasoning", "")

        return span.model_copy(update={
            "judge_score": score,
            "judge_reasoning": reasoning,
        })
    except Exception:
        return span.model_copy(update={
            "judge_score": None,
            "judge_reasoning": "Failed to parse judge response.",
        })


def judge_all_spans(spans: list[Span]) -> list[Span]:
    """Runs judge_span on every span in a trace. Simple sequential loop -
    fine for our sample sizes; could be parallelized later if needed."""
    return [judge_span(s) for s in spans]
