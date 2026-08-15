"""
Regression test for the judge fixes. Runs the EXACT invoice document
that exposed two real bugs (judge calling real fields "invented" on
extraction and summarization) through the FIXED pipeline, and prints
a clear pass/fail check against what we know is actually true about
this document.

This is not a synthetic sample - it's the real content that broke
things, used as a permanent regression case (the same "flashcard"
principle from the eval dataset, applied to our own pipeline code).

Run from project root:
    python test_judge_fix_regression.py
"""

from pipeline.traced_pipeline import run_traced_pipeline
from analysis.judge import judge_all_spans
from pipeline.storage import save_trace

INVOICE_TEXT = """
YAK SHAVING LTD
================
Company Number: 09522289

73 Douglas Buildings
Marshalsea Road
London
SE1 1EL
United Kingdom

+46 761 000 000
info@yakshavingltd.com

INVOICE

Invoice Number: 15000001
Invoice Date: 2015/04/01

To: Acme Rocket-Power Products, Inc.
    Anvil Department
    Fairfield
    New Jersey
    USA

DESCRIPTION: Wrought Iron Anvil | UNIT PRICE: 74 EUR | QUANTITY: 11 | AMOUNT: 814 EUR

Total: 814 EUR

VAT reverse-charged.

Payment should be made within 10 days by bank transfer.
Please transfer the total amount to:

BANK: HSBC BANK PLC
SORT CODE: 00-00-00
ACCOUNT NUMBER: 00000000
IBAN: GB00AAAA00000000000000
SWIFT: AAAAGB00
"""

# Ground truth facts we KNOW are true about this document, since we
# wrote/copied it ourselves. The judge should never claim these are
# "invented" or "not present" - if it does, the fix didn't work.
FACTS_THAT_MUST_NOT_BE_FLAGGED_AS_INVENTED = [
    "United Kingdom",
    "15000001",  # invoice number
    "814",       # total amount
    "HSBC",      # bank name
]


def main():
    print("Running the invoice that previously broke the judge...")
    print("(This will take 1-2 minutes - 3 pipeline calls + 3 judge calls on your local model)\n")

    trace = run_traced_pipeline("invoice_regression_test", INVOICE_TEXT)
    trace.spans = judge_all_spans(trace.spans)
    save_trace(trace)

    print(f"{'='*70}")
    print("RESULTS")
    print("=" * 70)

    any_problems = False

    for span in trace.spans:
        print(f"\n[{span.step_name}] SELF: {span.confidence}/5  JUDGE: {span.judge_score}/5")
        print(f"Judge reasoning: {span.judge_reasoning}")

        if span.judge_reasoning:
            reasoning_lower = span.judge_reasoning.lower()
            for fact in FACTS_THAT_MUST_NOT_BE_FLAGGED_AS_INVENTED:
                fact_lower = fact.lower()
                # crude but useful check: did the judge claim something
                # was invented/not-present WHILE also mentioning a fact
                # we know is genuinely in the source?
                if fact_lower in reasoning_lower and ("invented" in reasoning_lower or "not present" in reasoning_lower or "not explicitly stated" in reasoning_lower or "not directly supported" in reasoning_lower):
                    print(f"  ⚠ POSSIBLE REGRESSION: judge mentions '{fact}' alongside an 'invented/not present' claim - verify manually whether this is a real issue or a false positive in this simple keyword check.")
                    any_problems = True

    print(f"\n{'='*70}")
    if any_problems:
        print("REVIEW NEEDED: possible regressions flagged above - read the judge")
        print("reasoning text yourself to confirm whether the fix actually worked.")
    else:
        print("No obvious regressions detected by this automated check.")
        print("Still recommended: read the judge reasoning above yourself to confirm")
        print("it's making sound, well-grounded judgments - this script does a crude")
        print("keyword check, not a full correctness verification.")
    print("=" * 70)


if __name__ == "__main__":
    main()
