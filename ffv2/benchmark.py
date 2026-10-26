"""Reproducible injected mechanics benchmark. Never claim real-model accuracy."""

import argparse
import csv
import json
import hashlib
import platform
import random
import subprocess
from pathlib import Path

from ffv2.diagnosis import analyze, valid_citation
from ffv2.models import Attempt, Citation, Envelope, Issue, Judgment, Run

SCENARIOS = [
    "success",
    "extraction_propagation",
    "classification",
    "summary_only",
    "multiple",
    "timeout",
    "schema",
    "missing_judge",
    "false_allegation",
    "contradiction",
    "partial",
    "low_confidence_correct",
]


def fixtures():
    for family in range(6):
        for scenario in SCENARIOS:
            source = f"Total: {814 + family} EUR"
            run = Run(
                id=f"fixture-{family}-{scenario}",
                source=source,
                source_hash=f"synthetic-family-{family}",
                config={"execution_mode": "injected-fixture", "scenario": scenario},
            )
            expected = {
                "extraction_propagation": ["extract"],
                "classification": ["classify"],
                "summary_only": ["summarize"],
                "multiple": ["extract", "classify"],
                "timeout": ["extract"],
                "schema": ["extract"],
                "partial": ["extract"],
            }.get(scenario, [])
            for step in run.pipeline.steps:
                issue = (
                    step.id in expected
                    or (scenario == "extraction_propagation" and step.id == "summarize")
                    or (scenario in {"false_allegation", "contradiction"} and step.id == "extract")
                )
                propagated = scenario == "extraction_propagation" and step.id == "summarize"
                judgment = Judgment(
                    model="injected-not-inference",
                    assessment="issue" if issue else "acceptable",
                    source_correct=not issue,
                    input_faithful=propagated or not issue,
                    issues=[
                        Issue(
                            category="propagation"
                            if propagated
                            else "extraction"
                            if step.id == "extract"
                            else "misclassification"
                            if step.id == "classify"
                            else "unsupported_claim",
                            severity="high",
                            field="output",
                            rationale="Known synthetic injection",
                            citations=[
                                Citation(
                                    start=0,
                                    end=len(source),
                                    quote=source
                                    if scenario != "false_allegation"
                                    else "invalid quote",
                                )
                            ],
                            inherited_from=["extract"] if propagated else [],
                        )
                    ]
                    if issue
                    else [],
                    uncertainty="Fixture mechanics only",
                )
                if scenario == "contradiction" and step.id == "extract":
                    judgment.source_correct = True
                result = Envelope(
                    status="succeeded",
                    output={"confidence": 1 if scenario == "low_confidence_correct" else 5},
                    provider="fake",
                    model="fixture",
                )
                if scenario in {"timeout", "schema", "partial"} and step.id == "extract":
                    result.status = "failed"
                    result.error = "timeout" if scenario != "schema" else "invalid_schema"
                if scenario == "partial" and step.id == "summarize":
                    result.status = "skipped"
                run.attempts.append(
                    Attempt(
                        step_id=step.id,
                        dependencies=step.dependencies,
                        inputs={},
                        result=result,
                        judgment=None if scenario == "missing_judge" else judgment,
                    )
                )
            yield {
                "id": run.id,
                "family": run.source_hash,
                "split": "test" if family == 5 else "validation" if family == 4 else "development",
                "scenario": scenario,
                "expected": expected,
                "expected_categories": (
                    ["technical"]
                    if scenario in {"timeout", "partial"}
                    else ["schema"]
                    if scenario == "schema"
                    else sorted(
                        {
                            {
                                "extract": "extraction",
                                "classify": "misclassification",
                                "summarize": "unsupported_claim",
                            }[step]
                            for step in expected
                        }
                    )
                ),
                "ambiguous": scenario in {"missing_judge", "false_allegation", "contradiction"},
                "run": run,
            }


def scores(expected: set[str], predicted: set[str]) -> dict:
    return {
        "exact": int(expected == predicted),
        "precision": len(expected & predicted) / len(predicted)
        if predicted
        else (1.0 if not expected else 0.0),
        "recall": len(expected & predicted) / len(expected) if expected else 1.0,
    }


def legacy_prediction(run: Run) -> tuple[list[str], list[str]]:
    from analysis.root_cause import analyze_trace
    from pipeline.models import Span, Trace

    trace = Trace(
        trace_id=run.id,
        doc_id=run.id,
        spans=[
            Span(
                step_name={
                    "extract": "extraction",
                    "classify": "classification",
                    "summarize": "summarization",
                }[a.step_id],
                input_summary=run.source,
                output_summary="fixture",
                confidence=5,
                latency_seconds=0,
                llm_raw_response="",
                success=a.result.status == "succeeded",
                judge_score=2 if a.judgment and a.judgment.assessment == "issue" else 5,
                judge_reasoning="invented content"
                if a.judgment and a.judgment.assessment == "issue"
                else "correct",
            )
            for a in run.attempts
        ],
    )
    result = analyze_trace(trace)
    mapping = {"extraction": "extract", "classification": "classify", "summarization": "summarize"}
    category_mapping = {
        "extraction_hallucination": "extraction",
        "misclassification": "misclassification",
        "propagation_error": "propagation",
        "prompt_failure": "unsupported_claim",
        "context_loss": "omitted_context",
        "placeholder_as_data": "placeholder",
        "unclear": "unclear",
    }
    return (
        ([mapping[result.root_cause_step]], [category_mapping[result.category.value]])
        if result.root_cause_step
        else ([], [])
    )


def finding_categories(finding):
    return sorted(
        {
            ("schema" if item.get("technical_error") == "invalid_schema" else "technical")
            if item.get("technical_error")
            else item.get("category", "unclear")
            for item in finding.evidence
            if item["step_id"] in finding.origins
        }
    )


def category_macro_f1(rows):
    categories = sorted(
        {
            category
            for row in rows
            for category in row["expected_categories"] + row["predicted_categories"]
        }
    )
    values = []
    for category in categories:
        tp = sum(
            category in row["expected_categories"] and category in row["predicted_categories"]
            for row in rows
        )
        fp = sum(
            category not in row["expected_categories"] and category in row["predicted_categories"]
            for row in rows
        )
        fn = sum(
            category in row["expected_categories"] and category not in row["predicted_categories"]
            for row in rows
        )
        values.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    return sum(values) / len(values) if values else None


def benchmark(directory: Path | None) -> dict:
    rows = []
    for case in fixtures():
        run = case["run"]
        finding = analyze(run)
        without_source = analyze(run.model_copy(update={"source": ""}))
        graphless = run.model_copy(deep=True)
        for step in graphless.pipeline.steps:
            step.dependencies = ["document"]
        without_graph = analyze(graphless)
        rules = [a.step_id for a in run.attempts if a.result.status == "failed"]
        legacy_origins, legacy_categories = legacy_prediction(run)
        for name, prediction, abstain, predicted_categories in [
            (
                "graph",
                finding.origins,
                bool(finding.abstention_reason),
                finding_categories(finding),
            ),
            ("legacy_reverse_scan", legacy_origins, False, legacy_categories),
            (
                "technical_rules",
                rules,
                False,
                sorted(
                    {
                        "schema" if a.result.error == "invalid_schema" else "technical"
                        for a in run.attempts
                        if a.step_id in rules
                    }
                ),
            ),
            (
                "ablation_no_source",
                without_source.origins,
                bool(without_source.abstention_reason),
                finding_categories(without_source),
            ),
            (
                "ablation_no_graph",
                without_graph.origins,
                bool(without_graph.abstention_reason),
                finding_categories(without_graph),
            ),
        ]:
            rows.append(
                {
                    "case_id": case["id"],
                    "family": case["family"],
                    "split": case["split"],
                    "scenario": case["scenario"],
                    "analyzer": name,
                    "expected": case["expected"],
                    "expected_categories": case["expected_categories"],
                    "predicted_categories": predicted_categories,
                    "predicted": prediction,
                    "abstained": abstain,
                    "eligible": not case["ambiguous"],
                    **scores(set(case["expected"]), set(prediction)),
                }
            )
    metrics = {}
    rng = random.Random(42)
    for name in sorted({r["analyzer"] for r in rows}):
        eligible = [r for r in rows if r["analyzer"] == name and r["eligible"]]
        answered = [r for r in eligible if not r["abstained"]]
        families = sorted({r["family"] for r in eligible})
        samples = []
        for _ in range(500):
            sample = [
                r
                for family in rng.choices(families, k=len(families))
                for r in eligible
                if r["family"] == family
            ]
            samples.append(sum(r["exact"] for r in sample) / len(sample))
        samples.sort()
        metrics[name] = {
            "category_macro_f1": category_macro_f1(eligible),
            "eligible": len(eligible),
            "excluded_ambiguous": sum(r["analyzer"] == name and not r["eligible"] for r in rows),
            "mean_origin_precision": sum(r["precision"] for r in eligible) / len(eligible),
            "mean_origin_recall": sum(r["recall"] for r in eligible) / len(eligible),
            "false_positive_rate": sum(bool(r["predicted"]) for r in eligible if not r["expected"])
            / sum(not r["expected"] for r in eligible),
            "false_negative_rate": sum(not r["predicted"] for r in eligible if r["expected"])
            / sum(bool(r["expected"]) for r in eligible),
            "exact_set_match": sum(r["exact"] for r in eligible) / len(eligible),
            "coverage": len(answered) / len(eligible),
            "conditional_exact": sum(r["exact"] for r in answered) / len(answered)
            if answered
            else None,
            "family_bootstrap_95_interval": [samples[12], samples[487]],
            "per_scenario_counts": {
                s: sum(r["scenario"] == s for r in eligible) for s in SCENARIOS
            },
        }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable-in-packaged-image"
    report: dict = {
        "execution_mode": "synthetic_injected_mechanics_only",
        "dataset": "curated-mechanics-1",
        "cases": 72,
        "families": 6,
        "seed": 42,
        "commit": commit,
        "implementation_sha256": hashlib.sha256(
            Path(__file__).read_bytes() + Path(__file__).with_name("diagnosis.py").read_bytes()
        ).hexdigest(),
        "dataset_sha256": hashlib.sha256(
            json.dumps(
                [
                    {
                        key: case[key]
                        for key in (
                            "id",
                            "family",
                            "split",
                            "scenario",
                            "expected",
                            "expected_categories",
                            "ambiguous",
                        )
                    }
                    for case in fixtures()
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "model_identifiers": ["injected-not-inference"],
        "tokens": None,
        "provider_cost": None,
        "citation_validity": {
            "total": sum(
                len(issue.citations)
                for case in fixtures()
                for attempt in case["run"].attempts
                if attempt.judgment
                for issue in attempt.judgment.issues
            ),
            "valid": sum(
                valid_citation(citation, case["run"].source)
                for case in fixtures()
                for attempt in case["run"].attempts
                if attempt.judgment
                for issue in attempt.judgment.issues
                for citation in issue.citations
            ),
            "meaning": "Quote/offset validity only; not diagnosis correctness",
        },
        "hardware": platform.machine(),
        "platform": platform.system(),
        "concurrency": 1,
        "command": "uv run python -m ffv2.benchmark --output docs/benchmark",
        "metrics": metrics,
        "not_run": [
            "whole-trace real judge",
            "real producer/judge ablations",
            "human agreement",
            "real-model performance",
            "corrected-output scoring",
            "live latency/tokens/cost",
        ],
        "limitations": [
            "Six template families with twelve injected scenarios each; repeated mechanics are not independent real documents",
            "Intervals describe fixture family resampling, not population model accuracy",
            "No real human labels or model calls",
            "Ambiguous cases reported but excluded from exact-set scoring; abstention retained",
            "Frozen family split is metadata; no prompt tuning performed",
        ],
        "results": rows,
    }
    if directory is None:
        return report
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (directory / "results.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (directory / "report.md").write_text(
        "# Synthetic mechanics report\n\nNot a real-model accuracy benchmark.\n\n"
        + "\n".join(
            f"- {name}: {m['eligible']} eligible cases; exact-set match {m['exact_set_match']:.3f}; coverage {m['coverage']:.3f}."
            for name, m in sorted(metrics.items())
        )
        + "\n\n## Limitations\n\n"
        + "\n".join("- " + s for s in report["limitations"])
        + "\n\nNot run: "
        + ", ".join(report["not_run"])
        + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/benchmark"))
    args = parser.parse_args()
    report = benchmark(args.output)
    print(f"Generated {report['cases']} injected cases. Real model evaluation: NOT RUN.")
