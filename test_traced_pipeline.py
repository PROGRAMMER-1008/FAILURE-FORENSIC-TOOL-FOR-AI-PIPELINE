"""
Runs documents through the TRACED pipeline, saves the traces, then
loads them back to prove the storage round-trips correctly.

Run from project root:
    python test_traced_pipeline.py
"""

from pipeline.traced_pipeline import run_traced_pipeline
from pipeline.storage import save_trace, load_trace, list_traces

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
    saved_trace_ids = []

    for doc_id, text in SAMPLE_DOCS.items():
        print(f"\nRunning traced pipeline on: {doc_id}")
        trace = run_traced_pipeline(doc_id, text)

        print(f"  trace_id: {trace.trace_id}")
        print(f"  overall status: {trace.status.value}")
        for span in trace.spans:
            flag = " <-- LOW CONFIDENCE" if span.confidence <= 2 else ""
            print(f"    [{span.step_name}] confidence={span.confidence}/5, latency={span.latency_seconds:.2f}s{flag}")

        json_path = save_trace(trace)
        print(f"  saved to: {json_path}")
        saved_trace_ids.append(trace.trace_id)

    print("\n" + "=" * 60)
    print("Verifying storage round-trip (loading traces back)...")
    print("=" * 60)
    for tid in saved_trace_ids:
        reloaded = load_trace(tid)
        print(f"  Reloaded {tid[:8]}... doc_id={reloaded.doc_id}, spans={len(reloaded.spans)}, status={reloaded.status.value}")

    print("\n" + "=" * 60)
    print("Trace index (from SQLite):")
    print("=" * 60)
    for row in list_traces():
        print(f"  {row['trace_id'][:8]}... | {row['doc_id']} | {row['status']} | {row['created_at']}")


if __name__ == "__main__":
    main()
