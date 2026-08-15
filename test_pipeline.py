"""
Runs the pipeline end-to-end on a few sample documents.

Includes one "easy" document and one deliberately ambiguous one
(mixed signals about document type, vague dates) - we WANT this
one to potentially confuse the model, because we need real
failures to build the tracing/root-cause system against later.

Run from project root:
    python test_pipeline.py
"""

from pipeline.run_pipeline import run_pipeline

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
        print(f"\n{'='*60}")
        print(f"Processing: {doc_id}")
        print("=" * 60)

        output = run_pipeline(doc_id, text)

        print(f"\n--- Extraction (confidence: {output.extraction.confidence}/5) ---")
        for e in output.extraction.entities:
            print(f"  [{e.entity_type}] {e.name}: {e.value}")
        if not output.extraction.entities:
            print("  (no entities extracted)")

        print(f"\n--- Classification (confidence: {output.classification.confidence}/5) ---")
        print(f"  Type: {output.classification.document_type.value}")
        print(f"  Reasoning: {output.classification.reasoning}")

        print(f"\n--- Summary (confidence: {output.summary.confidence}/5) ---")
        print(f"  {output.summary.summary}")


if __name__ == "__main__":
    main()
