"""
Shows the current state of your growing eval dataset - the permanent
record of confirmed/corrected failures. Run this any time to see what
your review sessions have accumulated so far.

Run from project root:
    python view_eval_dataset.py
"""

from pipeline.storage import load_eval_dataset


def main():
    ground_truth = load_eval_dataset(ground_truth_only=True)
    all_cases = load_eval_dataset(ground_truth_only=False)
    unclear_count = len(all_cases) - len(ground_truth)

    print(f"Eval dataset summary:")
    print(f"  Ground truth cases (confirmed + corrected): {len(ground_truth)}")
    print(f"  Unclear cases (logged but excluded from ground truth): {unclear_count}")
    print(f"  Total reviewed: {len(all_cases)}")

    if not ground_truth:
        print("\nNo ground truth cases yet - run review_traces.py to start building the dataset.")
        return

    print(f"\n{'='*70}")
    print("Ground truth cases:")
    print("=" * 70)
    for case in ground_truth:
        print(f"\n[{case['verdict'].upper()}] {case['doc_id']} -> {case['failing_step']} ({case['failure_category']})")
        print(f"  Bad output:     {case['bad_output'][:100]}")
        print(f"  Correct output: {case['correct_output'][:100]}")
        if case['reviewer_notes']:
            print(f"  Notes: {case['reviewer_notes']}")


if __name__ == "__main__":
    main()
