"""
The human review flow. This is where YOU look at the analyzer's
candidate diagnosis plus the actual evidence, and decide: confirm,
correct, or mark unclear.

WHY THIS IS INTERACTIVE (asks questions in the terminal) RATHER THAN
AUTOMATIC:
This is the entire point of "human-in-the-loop" - the analyzer's
output is a DRAFT for a human to check, not a final answer. If we
auto-accepted every analyzer diagnosis, we'd just be trusting the
same imperfect signals we've already shown are noisy (self-confidence
inconsistent between runs, judge score not always matching its own
reasoning). The human is the actual source of truth here.

Run from project root:
    python review_traces.py
"""

import uuid
from datetime import datetime, timezone

from pipeline.storage import list_traces, load_trace, save_eval_case, mark_trace_flagged
from pipeline.models import EvalCase, ReviewVerdict
from analysis.root_cause import analyze_trace


def _get_span_output(trace, step_name: str) -> str:
    """Finds a span's output_summary by step name."""
    for span in trace.spans:
        if span.step_name == step_name:
            return span.output_summary
    return "(step not found)"


def review_one_trace(trace) -> bool:
    """
    Walks through reviewing one trace interactively. Returns True if
    an eval case was saved, False if skipped.
    """
    finding = analyze_trace(trace)

    print(f"\n{'='*70}")
    print(f"Document: {trace.doc_id}")
    print(f"Trace ID: {trace.trace_id}")
    print("=" * 70)
    print(f"\nOriginal document text:\n{trace.final_output.raw_document.raw_text}")

    if finding.root_cause_step is None:
        print("\nAnalyzer found no clear root cause for this trace (no suspect spans).")
        print("Nothing to review here - skipping.")
        return False

    print(f"\n--- Analyzer's candidate diagnosis ---")
    print(f"Root cause step : {finding.root_cause_step}")
    print(f"Category guess  : {finding.category.value}")
    print(f"Diagnosis conf. : {finding.confidence_in_diagnosis}")
    print(f"Evidence        : {finding.evidence}")

    bad_output = _get_span_output(trace, finding.root_cause_step)
    print(f"\nActual output from '{finding.root_cause_step}': {bad_output}")

    print("\n--- Your review ---")
    print("1 = Confirm (analyzer got it right)")
    print("2 = Correct (analyzer got something wrong, I'll provide the right answer)")
    print("3 = Unclear (I'm not confident enough to add this as ground truth)")
    print("4 = Skip this trace entirely")

    choice = input("Your choice (1-4): ").strip()

    if choice == "4":
        print("Skipped.")
        return False

    if choice == "1":
        verdict = ReviewVerdict.CONFIRMED
        category = finding.category.value
        notes = input("Any notes (optional, press enter to skip): ").strip()
        correct_output = input("What SHOULD the correct output have been? ").strip()

    elif choice == "2":
        verdict = ReviewVerdict.CORRECTED
        print("What's the correct failure category? Options:")
        print("  extraction_hallucination, misclassification, propagation_error,")
        print("  prompt_failure, context_loss, placeholder_as_data, unclear")
        category = input("Correct category: ").strip()
        correct_output = input("What SHOULD the correct output have been? ").strip()
        notes = input("Notes on what the analyzer got wrong: ").strip()

    elif choice == "3":
        verdict = ReviewVerdict.UNCLEAR
        category = finding.category.value
        correct_output = ""
        notes = input("Why is this unclear? (optional): ").strip()

    else:
        print("Invalid choice, skipping.")
        return False

    case = EvalCase(
        eval_case_id=str(uuid.uuid4()),
        source_trace_id=trace.trace_id,
        doc_id=trace.doc_id,
        original_input_text=trace.final_output.raw_document.raw_text,
        failing_step=finding.root_cause_step,
        bad_output=bad_output,
        correct_output=correct_output,
        failure_category=category,
        verdict=verdict,
        reviewer_notes=notes,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_eval_case(case)
    mark_trace_flagged(trace.trace_id)
    print(f"\nSaved as eval case ({verdict.value}). This will now be part of your growing eval dataset.")
    return True


def main():
    trace_rows = list_traces()
    if not trace_rows:
        print("No saved traces found. Run test_judge.py first to generate some.")
        return

    print(f"Found {len(trace_rows)} saved traces. Reviewing traces with judge data...\n")

    saved_count = 0
    for row in trace_rows:
        trace = load_trace(row["trace_id"])
        if all(s.judge_score is None for s in trace.spans):
            continue  # skip traces without judge data - nothing to analyze
        if review_one_trace(trace):
            saved_count += 1

    print(f"\n\nReview session complete. {saved_count} new eval case(s) saved.")


if __name__ == "__main__":
    main()
