# Synthetic mechanics report

Not a real-model accuracy benchmark.

- ablation_no_graph: 54 eligible cases; exact-set match 1.000; coverage 0.889.
- ablation_no_source: 54 eligible cases; exact-set match 0.556; coverage 0.556.
- graph: 54 eligible cases; exact-set match 1.000; coverage 1.000.
- legacy_reverse_scan: 54 eligible cases; exact-set match 0.778; coverage 1.000.
- technical_rules: 54 eligible cases; exact-set match 0.556; coverage 1.000.

## Limitations

- Six template families with twelve injected scenarios each; repeated mechanics are not independent real documents
- Intervals describe fixture family resampling, not population model accuracy
- No real human labels or model calls
- Ambiguous cases reported but excluded from exact-set scoring; abstention retained
- Frozen family split is metadata; no prompt tuning performed

Not run: whole-trace real judge, real producer/judge ablations, human agreement, real-model performance, corrected-output scoring, live latency/tokens/cost
