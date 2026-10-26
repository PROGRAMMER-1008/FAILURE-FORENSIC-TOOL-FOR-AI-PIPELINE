# Evaluation and dataset card

`uv run python -m ffv2.benchmark` generates [the report](benchmark/report.md), JSON and CSV from actual fixture results.

Dataset `curated-mechanics-1`: 72 injected fixtures, six invented template families, twelve scenarios each. Families 0–3 development, 4 validation, 5 test. All related scenarios remain in one family split. These are repeated mechanics checks, not 72 independent real-world documents. No human labels are fabricated.

Scenarios: successful run, extraction propagation, independent classification failure, summary-only error, multiple origins, timeout, schema error, missing judge, unsupported allegation, contradictory evidence, partial run, and low self-confidence with correct output. Original invoice regression motivates preserving full entity values but its private source is not reused.

Compared: actual legacy reverse-scan implementation, technical-failure rules baseline, graph/evidence analyzer, plus no-source and no-graph ablations. The whole-trace real judge and same/separate-model ablations remain not run. Exact-set origin match, origin precision/recall, category macro-F1, fixture false-positive/false-negative rates, coverage and conditional exact match are computed. Ambiguous cases are retained in results and excluded explicitly from eligible exact-set scoring. Family bootstrap intervals use seed 42. Citation validity is reported separately from diagnosis correctness. Reports include dataset and implementation hashes, model identifiers and unknown token/cost fields. These fixture rates are not population estimates. Exact-field replay scoring is implemented only for explicit expected outputs. Live latency/tokens/cost and repeated real-model counterfactual trials remain unmeasured.

Real annotation workflow: run with local Ollama, review source and outputs, record reviewer identity/provenance and uncertainty, optionally collect an independent second review. Conflicting labels are unresolved. Freeze feedback snapshots separately; do not tune against the frozen fixture test family. Agreement is reported only after actual independent annotation. An LLM suggestion is never gold output.

Recorded replay means viewing saved artifacts, without new inference. Re-execution can replace a validated human-provided step output and rerun descendants; an unchanged control rerun is available. Seeds do not guarantee identical real model outputs. Without explicit gold output/assertions, output-quality scoring is unavailable. Improved synthetic outputs do not establish real-world causality.
