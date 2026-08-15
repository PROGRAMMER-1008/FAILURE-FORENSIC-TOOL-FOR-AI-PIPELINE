"""
Runs root-cause analysis on traces already saved to disk from your
earlier test_judge.py runs (data/traces/*.json).

Run from project root:
    python test_root_cause.py
"""

from pipeline.storage import list_traces, load_trace
from analysis.root_cause import analyze_trace


def main():
    trace_rows = list_traces()

    if not trace_rows:
        print("No saved traces found. Run test_judge.py first.")
        return

    for row in trace_rows:
        trace = load_trace(row["trace_id"])

        # Skip traces that don't have judge data yet (e.g. from
        # test_traced_pipeline.py before we added judging)
        if all(s.judge_score is None for s in trace.spans):
            print(f"\nSkipping {trace.doc_id} (trace_id={trace.trace_id[:8]}...) - no judge data.")
            continue

        print(f"\n{'='*70}")
        print(f"Trace: {trace.doc_id}  ({trace.trace_id[:8]}...)")
        print("=" * 70)

        finding = analyze_trace(trace)

        if finding.root_cause_step is None:
            print("Root cause: none found (no span showed clear problem evidence)")
        else:
            print(f"Root cause step:    {finding.root_cause_step}")
            print(f"Failure category:   {finding.category.value}")
            print(f"Diagnosis confidence: {finding.confidence_in_diagnosis}")
            print(f"Evidence: {finding.evidence}")
            if finding.downstream_steps_affected:
                print(f"Likely-affected downstream steps: {', '.join(finding.downstream_steps_affected)}")
            else:
                print("Downstream steps affected: none (root cause was the last step)")


if __name__ == "__main__":
    main()
