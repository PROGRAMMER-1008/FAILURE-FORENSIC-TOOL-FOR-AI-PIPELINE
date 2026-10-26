# Baseline audit — 18 October 2026

Initial branch: main, commit 64a3e06. Only untracked change: the owner's implementation prompt.
No applicable first-party AGENTS.md found. No environment secrets read.

| Brief claim | Source observation |
| --- | --- |
| Reverse scan selects last suspect | root_cause.py reverses spans and breaks; descendants use list order. |
| Classification is independent | step_classification.py receives only RawDocument. |
| Hidden execution errors | Three steps return fallbacks; traced pipeline hardcodes success. Scores are clamped. |
| Raw text reconstructed | traced_pipeline explicitly documents reconstruction. |
| Entity value missing | Summary prompt and entity display omit value. |
| Judge sees producer rationale | Classification output_summary includes reasoning. |
| Blocking upload route | async analyze reads all bytes, calls synchronous pipeline, saves last. |
| Dual mutable storage | JSON write then SQLite INSERT OR REPLACE; created_at resets. |
| Unbounded lists/stats | server loads every trace and computes analysis. |
| Review defects | loose dict, finding required, fixed origin, every verdict flags bad; no idempotency. |
| Parser limits missing | paragraphs only in DOCX; no byte/page/expansion limits. |
| Deployment boundary absent | wildcard CORS; no authentication. |

7,793 tracked files under forensic/; pyvenv.cfg identifies Python 3.10.11. Tree contains Lib, Scripts and Include. Verified as a virtual environment, removed from index only. Local files preserved; no bundled binaries executed.

Most legacy demonstrations have main guards, but test_llm_client.py calls inference on import. Move demos to examples/ and guard that call. Existing invoice regression explicitly says its document was real. Committed trace privacy/provenance remains unverified: do not reuse in demos or publishing. Preserve originals. Use invented fixtures for new tests.

No tracked .env paths found in Git metadata. This is not a history secret audit. No new license chosen.

Runtime discovery: system Python 3.10, uv 0.11.16, Node 20.20.2. Docker client exists; initial sandbox daemon access denied. Create Python 3.12 environment independently of forensic/.
