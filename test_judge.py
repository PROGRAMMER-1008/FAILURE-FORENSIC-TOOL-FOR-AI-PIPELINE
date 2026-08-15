"""
Runs the traced pipeline, then runs the independent judge on every span,
and prints a side-by-side comparison of self-confidence vs judge score.
This comparison IS the interesting data - agreement vs disagreement
between the two signals.

Run from project root:
    python test_judge.py
"""

from pipeline.traced_pipeline import run_traced_pipeline
from analysis.judge import judge_all_spans
from pipeline.storage import save_trace

SAMPLE_DOCS = {
    "doc_001_invoice": """
INVOICE #INV-2024-0587
Date: March 15, 2024
Bill To: Rajesh Enterprises, Sector 14, Gurugram
From: TechSupply Solutions Pvt Ltd

Item: Laptop batteries (x50) - Rs. 45,000
Item: Charging cables (x100) - Rs. 12,000

Subtotal: Rs. 57,000
Tax (18% GST): Rs. 10,260
Total Due: Rs. 67,260

Payment Terms: Net 30 days
""",

    "doc_002_ambiguous": """
Re: Service Agreement Update

Following our discussion, please find the revised terms below. This
supersedes the previous arrangement dated sometime last quarter. The
vendor (name to be confirmed) will provide ongoing support services.
Payment shall be made upon delivery of milestones, amount TBD pending
final scope. Both parties agree to review this in Q3.

Signed,
The Team
""",
}


def main():
    for doc_id, text in SAMPLE_DOCS.items():
        print(f"\n{'='*70}")
        print(f"Document: {doc_id}")
        print("=" * 70)

        trace = run_traced_pipeline(doc_id, text)
        judged_spans = judge_all_spans(trace.spans)
        trace.spans = judged_spans  # replace with judged versions

        print(f"{'Step':<16}{'Self-Conf':<12}{'Judge':<10}{'Agree?':<10}Judge reasoning")
        print("-" * 100)
        for span in trace.spans:
            agree = "—"
            if span.judge_score is not None:
                diff = abs(span.confidence - span.judge_score)
                agree = "yes" if diff <= 1 else "DISAGREE"
            judge_str = str(span.judge_score) if span.judge_score is not None else "FAILED"
            print(f"{span.step_name:<16}{span.confidence:<12}{judge_str:<10}{agree:<10}{span.judge_reasoning}")

        save_trace(trace)


if __name__ == "__main__":
    main()
