# Implementation status

Incremental implementation; no claim of completion or production readiness.

| Phase | Status | Remaining acceptance |
| --- | --- | --- |
| 0 baseline | Initial acceptance passed | Clean locked Python setup; deterministic collection; index hygiene; limited redacted scanner. Historical privacy/secret review remains manual. |
| 1 tracing/storage | Core acceptance verified | Strict envelopes and sanitized validation locations; transactional schema; immutable migration snapshot; timestamps; partial attempts; stable-ID trace/eval-case importer. Legacy labels preserve provenance as unverified. Earlier real PostgreSQL claim/fencing test passed; latest rerun blocked by stopped Docker daemon. |
| 2 diagnosis | Deterministic acceptance verified | Structured source citations, actual DAG, multi-origin/propagation/abstention fixtures. Live judge correctness is not measured. No cache implemented. |
| 3 execution/API | Core acceptance verified | Separate worker, transactionally enqueued jobs, leases/fencing, bounded retries, process-kill recovery, cancellation race, SSE replay, bounded isolated uploads. Distributed rate limiting and full parser memory sandbox remain outside current local validation. |
| 4 UI/review | Core workflow verified | React build/lint and two component tests passed. Expanded browser submit→inspect→review→replay comparison→dataset freeze/export→experiment→refresh passed. Wide/narrow screenshots inspected; axe found no violations on tested detail page. Search/time/order filters implemented. |
| 5 evaluation | Synthetic mechanics verified | 72 cases / 6 families; actual legacy/rules/graph comparison, source/graph ablations, origin metrics, category macro-F1, citation validity, family bootstrap intervals, report hashes, explicit-output replay scorer. Real whole-trace/same-vs-separate judge measurements and independent human agreement unavailable. |
| 6 operations | Container build/readiness passed in GitHub CI; hosted checks remain | SQLite restore and explicit snapshot privacy deletion tested. Server-enforced demo and proxy/subject boundary tested. PostgreSQL restore and real hosted OIDC/TLS remain unverified. |
| 7 verification | Local and GitHub CI passed; hosted acceptance outstanding | Latest local: 49 backend tests passed, 2 explicit skips; 9 component tests, build/lint/type checks passed. GitHub CI for 3e9dedc passed backend with PostgreSQL, frontend, container and browser jobs. Full AI hosting remains undeployed. |

## Verification log

- `git status --short`: initially only untracked implementation prompt.
- `git switch -c codex/failure-forensics-v2`: succeeded after sandbox elevation.
- `git rm -r --cached --quiet forensic`: succeeded; index only, local files preserved.
- `docker info --format '{{.ServerVersion}}'`: sandbox pipe access denied; not passed.

## Verification evidence accumulated on 18 October 2026

- Fresh `.venv` created from Python 3.12.10 and uv.lock; no forensic/ binary used.
- Initial 2 socket-disabled tests passed, then 13 tracing/import tests, then 22 diagnosis/worker tests, then 25 API/upload tests.
- Latest completed full suite: `.venv/Scripts/python -m pytest --basetemp=.test-tmp/check12`: **35 passed, 2 skipped**. Skips are explicit PostgreSQL/live opt-ins; later edits are being revalidated.
- `.venv/Scripts/python -m mypy`: **19 source files, no issues**. Ruff check/format passed.
- Real PostgreSQL 17.5: `FF_TEST_DATABASE_URL` pointed to a disposable loopback container; `pytest tests/test_postgres.py`: **1 passed** (competing claims, lease expiry, stale write fencing). No user DB touched.
- Worker kill test terminates a child mid-call, verifies persisted running attempt, expires lease and recovers to a second attempt. Passed. Cancellation commit-race and transaction rollback tests added.
- `npm run build`, `npm run lint`: passed. Node now pinned to 22.22.2 for current test dependency compatibility; global Node was not changed.
- `npm test`: **2 component tests passed**, including hostile reviewer text rendered safely and demo controls disabled.
- `npm run e2e` with FF_BROWSER_URL=http://127.0.0.1:18765: **1 passed**, submit/review/replay, wide/narrow screenshots, no horizontal overflow, zero axe violations on inspected detail page. Not a full accessibility certification.
- `docker build -t failure-forensics:v2-local .`: passed before latest dependency/UI additions; rebuild queued. Image `id` returned uid/gid 10001. Migration, /health/ready=200 and container restart smoke passed.
- Python dependency audit initially found vulnerable pins; upgraded FastAPI/Starlette, pypdf, multipart, pytest and compatible telemetry. Latest pip-audit: **no known vulnerabilities found**. Latest npm audit: **0 vulnerabilities**. These are database snapshots, not security guarantees.
- `python -m ffv2.benchmark`: generated 72 injected cases with reproducible report files. No inference/human labels.
- `python -m scripts.performance --database .test-tmp/performance-v1.db`: 10,000 summaries; 200 in-process requests, concurrency 4, 0 errors; p50 49.94ms / p95 60.96ms / p99 73.98ms; peak Python tracked allocation 2,272,308 bytes. See performance.json for hardware/limits. Not production network capacity or simultaneous-model load.
- `python -m scripts.provider_status`: local Ollama unreachable (URLError), inference not run. Real-model acceptance blocked until Ollama/model hardware is available.
- `python scripts/scan_secrets.py`: 0 matches in limited source scan. .env/data excluded, history not audited.

## Preservation and limitations

The only initial user change was the untracked implementation prompt, which remains untouched. Local forensic/ files and legacy data remain on disk. Index-only removals include 7,793 virtual-environment files and three unverified legacy trace JSON files. Legacy README preserved in docs/legacy-readme.md. Existing .env files were never opened or modified.

Playwright's first installer automatically removed old shared browser caches. Restored exact removed revisions with garbage collection disabled: Chromium/headless 1148, Chromium/headless 1208, headless 1234, Firefox 1466, WebKit 2104 and ffmpeg 1011. Subsequent install instructions set PLAYWRIGHT_SKIP_BROWSER_GC=1. New caches/runtime tools are isolated additions; global Node unchanged.

Remaining real/manual dependencies: reachable Ollama and installed models; actual independent human annotations/adjudication; configured OIDC provider/proxy/TLS; owner licensing/privacy decisions; explicit authorization for publication/deployment. No numeric real-model improvement, human agreement, deployed service or production capacity claimed.

## Latest verification and exact blockers

- Final backend command: `.venv/Scripts/python -m pytest --basetemp=.test-tmp/check15` → **40 passed, 2 skipped**, 3.40 seconds. PostgreSQL test skipped without its opt-in URL; live test skipped without FF_LIVE_TEST=1. Skips are not passes.
- Ruff check/format and mypy passed after all application edits; mypy checked 19 v2 source files.
- Expanded browser command: `FF_BROWSER_URL=http://127.0.0.1:18765 npm run e2e` → **1 passed**, 5.9 seconds. Includes dataset freezing/export, synthetic experiment and browser refresh in addition to investigation/review/replay. Component tests: **2 passed**.
- Active-job infrastructure command: `python -m scripts.performance --database .test-tmp/performance-v2.db` → 10,000 summaries, 200 requests, concurrency 4, **0 errors**, 75 requests started while the synthetic worker ran; p50 42.52ms / p95 89.97ms / p99 132.33ms, peak Python tracked allocation 2,735,391 bytes. Injected 250ms fake-call delay; no real inference. Latest JSON overwrites the earlier no-worker measurement and is authoritative.
- Docker became unavailable during the later PostgreSQL rerun: `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`. The stalled test process was stopped, DB connection timeout bounded to 5 seconds, independent tests completed. **Do not treat the earlier image/PostgreSQL results as a final-tree container/concurrency pass.**
- Once Docker is running, reproduce: `docker build -t failure-forensics:v2-local .`; run disposable PostgreSQL with FF_TEST_DATABASE_URL and `pytest tests/test_postgres.py`; exercise `scripts.postgres_backup restore-new` against a fresh DB. The new nginx and private-auth examples also need deployment-specific validation.
- Local Ollama endpoint 127.0.0.1:11434 was unreachable (URLError). One-call live smoke test is opt-in with a 30-second deadline; whole-trace/model ablations cannot be honestly measured without the service/model.
- Git whitespace check and limited redacted source scan passed. `.env` contents were not read. No commits, push, image publication, paid provisioning or history rewrite.

## Remaining acceptance limitations (not hidden as completed)

- Real provider/judge accuracy, separately configured model comparisons, repeated counterfactual trials and actual human agreement require external model/human evidence.
- Final-tree PostgreSQL/container/proxy smoke and PostgreSQL backup restore await Docker availability. Real OIDC cookie expiry/CSRF/TLS flows require owner identity/TLS configuration.
- Telemetry counters are process-local; production metrics aggregation and operational alert delivery are examples, not deployed monitoring.
- Parser isolation has a time/size bound but no Windows OS memory sandbox. Hosted resource quotas must be configured and tested.
- Browser evidence covers one main workflow and the inspected responsive layouts, not every assistive technology/offline/session-expiry combination.
- This is a local development application with explicit limitations, not a certified or deployed production service. Remote CI workflow files have not run because nothing was pushed.

Session-created resources: `.venv`, `.uv-cache`, ignored synthetic test DBs and test outputs; Docker images and disposable containers `ff-v2-test-db`, `ff-v2-smoke`. Docker was unavailable for final cleanup; when it returns those two synthetic-only containers may be removed with `docker rm -f ff-v2-test-db ff-v2-smoke`. No user volumes were mounted into them.

The session's loopback browser-test API and worker were stopped at handoff. Use README startup commands to launch the application deliberately.

No push, publication, provisioning, model downloads or history rewrite. Existing .env files untouched.

## Usability and visual refinement — 2026-10-18

Completed a further UI pass on codex/failure-forensics-v2, retaining React 19/TypeScript/Vite and adding no runtime dependencies:
- Violet/cyan workspace styling, clearer typography, rounded panels, colored execution badges and responsive introductory workflow cards.
- Plain-language step and review labels. Overview explains the document → evidence → review/replay workflow and distinguishes suspected origins from symptoms.
- Readable nested output fields in the investigation and original/replay comparison; raw structured output remains available for inspection. Zero/false values and hostile strings are preserved safely as text.
- Removed the hard-coded invoice correction from every investigation. Replay starts blank and disabled; users explicitly copy the current run's extraction, edit it, and submit. Review notes, expected outputs, correction and history reset when changing investigations.
- Refreshed desktop/mobile evidence in docs/screenshots.

Verification: pinned Node 22.22.2 frontend production build passed; ESLint passed; Vitest 4/4 passed. Expanded Playwright workflow passed (6.3 seconds total), including disabled blank correction, copying the recorded 999 value and explicitly changing it to 814, review, replay, comparison, dataset freeze/export and persisted synthetic experiment. Axe reported zero violations on the investigation page. Mobile 390px overflow assertion passed; desktop/mobile screenshots visually inspected. These checks cover the synthetic local workflow, not all assistive technologies or real provider accuracy. Backend code was unchanged in this pass, so its preceding verification and external limitations still apply.

Remaining: advanced expected-output and correction editing still uses JSON; real-model/OIDC/container acceptance remains subject to the external dependencies documented above. No .env values read, publication, push, paid provisioning or Git history rewrite. Test API and worker stopped after verification.

## Interactive preview started — 2026-10-18

At the user's request, started the API at http://127.0.0.1:8000 and the synthetic worker as hidden background processes. Dedicated database: data/local-preview.db; explicitly migrated with Alembic. Process configuration: FF_MODE=local, FF_PROVIDER=fake, FF_DATABASE_URL=sqlite:///data/local-preview.db. No .env read or modified. API PID 20264, worker PID 8312 at launch; both confirmed running. Console and /health/ready returned HTTP 200. Services deliberately remain running for user testing (supersedes the previous test-service shutdown note). Preview uses synthetic outputs; arbitrary uploaded documents are not meaningfully analyzed by this provider.

## Groq provider integration — 2026-10-18

Added Groq HTTPS chat-completions adapter for producer and judge, JSON object output with existing strict local schema/citation validation, completion token tracking, deadlines, sanitized errors and explicit provider selection. No added dependencies. SecretStr masks the key in settings representations; API/config/run metadata use explicit allowlisted fields, not the settings object. Groq key is supplied as FF_GROQ_API_KEY; no .env read or modification. Browser labels distinguish Groq cloud from local Ollama; submission notice explains cloud transfer and quota usage. Synthetic error injection is disabled in cloud mode.

Added scripts/start_groq.py: interactive hidden key entry, user-selectable model default openai/gpt-oss-20b, separate groq-preview.db and port 8001, child lifecycle cleanup on Ctrl+C. Keeps existing port 8000 synthetic preview unchanged. Key never written to files or command arguments. Launcher itself is not run by the agent because user-owned interactive credential input is required.

Verification: Ruff and mypy passed; full pytest 45 passed, 2 skipped (live Ollama and PostgreSQL external opt-ins). Five Groq tests cover authenticated request structure/token capture/producer-judge selection, missing credential, and sanitized 401/429/500 handling using MockTransport with no live calls. Frontend build and lint passed. Actual Groq connectivity/model access/quality remain UNVERIFIED until the user runs with their credential. No API charges, external document transmission, provisioning, push or publication performed by this change.

## Local AI setup completed — 2026-10-21

- Created root .env using exclusive-create with a blank Groq key and FF_PROVIDER=fake; no existing file was overwritten or read. git check-ignore confirms .env exclusion, and .dockerignore excludes it from images.
- Added start-local.cmd and ffv2.local: explicitly load the root .env, apply process-environment precedence, migrate and start API/worker with the same configuration, check readiness, detect occupied port, and stop child processes on Ctrl+C. Default address is http://127.0.0.1:8001; template database is data/local-ai.db. Existing preview/legacy databases are preserved. Direct service commands remain environment-only.
- Missing Groq key allows setup browsing but starts no worker and rejects submissions/uploads and Groq re-execution. Config API exposes credential presence only, explicitly unverified, never the value. UI explains local setup, cloud transfer, restart requirements and model choices; no browser credential input or key persistence endpoint added. Reviews/cancellation remain usable without a key.
- README and configuration guide updated. Earlier historical notes about no .env reflect the state before this requested setup.

Verification: pytest check18: 49 passed, 2 skipped (live provider and PostgreSQL opt-ins); Ruff and mypy (20 files) passed; frontend production build, ESLint and 4 component tests passed. Playwright: 2 passed, including synthetic end-to-end workflow and missing-key setup, disabled submission, unchecked injection, mobile overflow and axe accessibility. Initial axe inline-link issue fixed with persistent underlines and checks rerun successfully. Launcher startup/readiness/shutdown smoke passed on port 18766 with an explicit synthetic Settings override and a separate data/launcher-smoke.db; this test did not read the project's .env. Dotenv parsing and precedence tested only against temporary test files with dummy values.

Real Groq authentication/model access/quality are still unverified until the owner supplies a key and submits a document. No cloud calls, model downloads, charges, publication, push or history changes performed. Browser verification processes stopped after checks. Use start-local.cmd deliberately when ready; keep its terminal open and restart after configuration changes.

## Pipeline flowchart refinement — 2026-10-21

User reports Groq works with their configured key; no credential values inspected or live Groq calls made during this change. Replaced the only text-drawn dependency diagram found in frontend/src with PipelineGraph: SVG connectors/arrowheads, native keyboard-accessible step buttons, recorded execution statuses, suspected-origin/symptom labels and selected-path highlighting. Edges are filtered by the stored run pipeline dependencies for the current extract/classify/summarize pipeline. Desktop uses a branching horizontal layout; container-responsive mobile layout uses vertical branches and a separate direct source-to-summary lane. Added a readable dependency list as an accessible alternative. Existing navigation arrows are links, not diagrams, and remain intact. No new dependencies.

Verification: production build and ESLint passed; 6 component tests passed, including edge filtering and node selection. Both Playwright tests passed (14.5 seconds), covering five graph edges, click/keyboard selection, desktop/mobile axe scans, 390px layout/no overflow, synthetic review/replay/dataset/experiment workflow and missing-key setup. Visual inspection caught a mobile direct edge crossing a node; spacing corrected and screenshot rechecked. Accessible names were corrected to use the visible label text in order. Updated screenshots in docs/screenshots, including focused flowchart-wide.png and flowchart-narrow.png. No backend changes; preceding backend verification still applies. Test API/worker stopped after checking; user Groq service/configuration untouched.

## Guided investigation usability — 2026-10-21

Added a plain-language start-here summary that separates processing success from factual correctness, names possible starting points/downstream symptoms, and explains the next action. Missing findings remain inconclusive. Numbered investigation sections guide users through the graph, source/output comparison, human review and optional correction. Original text is now readable beside the selected output. Technical evidence and optional expected-answer JSON are progressively disclosed.

Replaced comma-separated origin IDs with labelled checkboxes. Review defaults to unsure with no preselected origin and resets on run navigation. Added a simple correction field editor for extracted values; it preserves other contract fields and supports advanced JSON for adding/removing facts. Renamed actions to Copy facts to edit, Run with my correction, and Run again without changes. Malformed advanced JSON shows a local explanation instead of crashing the page.

Verification: production build and lint passed; 9 component tests passed (including missing-finding wording, correction preservation and malformed JSON). Final Playwright run: 2 passed in 10.4 seconds, including intentional origin selection, review saving, correction via a normal input, replay/comparison, dataset/experiment workflow, missing-key setup, keyboard navigation, desktop/mobile accessibility and no horizontal overflow. Desktop/mobile screenshots visually inspected and refreshed. Backend unchanged. Synthetic test services stopped; no .env/key read, Groq call, user-service interruption or publication.


## LinkedIn launch kit and public sample — 2026-10-25

Completed a separate polished public showcase with responsive SVG dependency graph, selectable recorded outputs, invented source evidence, validated browser-only correction exercise and explicit sample/full-app scope. Published with Sites at https://failure-forensics-lab.niftygnat2.chatgpt.site; deployment appgdep_6ade184afea881918befea6fbb7663fe returned succeeded, audience public. Only the separate public-demo source was synchronized by the Sites helper (commit 6a68a236d5acc112024a69b535803c7d4ad23e37); main repository was not pushed or committed. Publication was explicitly requested by the user, superseding the earlier no-publication constraint for this showcase.

Recorded the actual local app against a dedicated synthetic database and worker, covering submission, evidence graph, human review, simple correction, replay comparison and versioned dataset. Saved launch/failure-forensics-demo.mp4 and original WebM, cover, chapter timings, optional SRT captions, desktop/mobile showcase screenshots, deployment instructions and a LinkedIn post based on the owner's stated month-long from-scratch work. No LinkedIn post sent.

Verification: public demo Playwright interaction/input validation/original preservation/reset checks passed; axe zero violations on desktop and mobile; no horizontal overflow or browser errors. Desktop/mobile screenshots and final video contact sheet visually inspected. MP4 metadata confirms 57.64 seconds, H.264, yuv420p, 1280x800 at 25 fps, silent. Recording exercised actual local synthetic review/replay/dataset behavior. No main app runtime changes; previous backend/frontend verification applies. The public deployment service confirms successful publication; a full hosted Python backend was not deployed or tested.

Remaining limitations: public correction is a simulation over invented data, not live inference. Real Groq works according to the owner; no credential read or agent live-provider call performed. Full API/worker hosting, production authentication, PostgreSQL/container acceptance and real-provider evaluation remain separate work with the external dependencies previously documented. No paid resources provisioned; existing local environment preserved.

Final cleanup: stopped only temporary recording API/worker and static-preview processes (32688, 19180, 22728) after executable-path verification. Full MP4 decode completed successfully with FFmpeg; git diff whitespace check passed for the touched launch/status/script paths. User Groq service was not stopped.


## Live Groq recording and personal-hosting preparation — 2026-10-25

Verified the existing Groq implementation with an actual request through the full app. Used normal runtime configuration loading (no secret inspection/output), forced local/Groq mode and a separate data/groq-recording-20261025.db on loopback 18769. Owner authorized real AI recording. No injected error or mock inference. Run e0fba85d-90b7-4a5a-8191-d3141dbfc59c completed all three producer steps with Groq openai/gpt-oss-20b. Extraction returned 814 EUR and classification invoice. Summary evaluator citation validation failed; quality correctly remained inconclusive. No real-model accuracy claim is made.

Added reusable frontend/scripts/record-groq-demo.mjs, recorded and exported launch/failure-forensics-groq-demo.mp4 (61.96 seconds, H.264/yuv420p, 1280x800, 25 fps, silent captions), original WebM, cover, chapter timing and invented-run evidence. Contact sheet visually inspected and full MP4 decode passed. Saved an alternate LinkedIn draft for this real AI video. No changes to main application behavior were necessary because Groq integration already existed.

Prepared isolated launch/vercel-sample with only static assets and Vercel configuration, removing the previous host from the image metadata. User selected their Vercel account for a vercel.app address. CLI 65.2.0 reports signed out; browser/device sign-in started. New URL remains pending until the owner completes authentication and deployment succeeds. Existing Sites URL remains live; full AI backend is not publicly deployed. No paid resources requested, no main repo push/history rewrite, no credential values exposed.

Recording launcher session ended after capture. The existing user Groq configuration and earlier app sessions were not modified. Vercel deployment is awaiting user device authentication.


## Vercel publication completed — 2026-10-26

User completed Vercel device sign-in. Static sample deployed under owner scope pk-1086/project vercel-sample; deployment dpl_H6L9pcvF64yK47FuiSNm565Z85Wo returned READY. Branded alias: https://failure-forensics-pk.vercel.app. Vercel automatically attempted to connect the parent GitHub repository but that connection failed; direct static deployment succeeded. No main repository push or Git history change occurred. Automatic Git deployment is not configured.

Initial anonymous browser check detected a login requirement on the manually assigned alias (default production URL was already public). Disabled Vercel Authentication for this public static sample project only. Final signed-out Playwright check at the branded alias passed: output selection, 814 correction, unchanged original 999, invalid empty input, reset, desktop/mobile axe zero violations, no horizontal overflow and no JS errors. QA screenshots refreshed. Updated both LinkedIn drafts and launch documentation with the verified branded URL. Existing Sites deployment remains available.

Live Groq functionality was verified in the preceding recorded local run; the Vercel sample itself performs no live inference. Full backend hosting remains outside this completed static deployment. No secret values inspected or published, no paid resources requested, and no LinkedIn post sent.


## Repository-first sharing release — 2026-10-26

User authorized pushing the existing GitHub repository and prefers sharing it with the real Groq video instead of the synthetic website. Fetched origin: main remains 64a3e06 with no remote changes beyond the local base. Prepared a clean development release on codex/failure-forensics-v2, preserving index-only removal of the legacy virtual environment and private trace files (local files remain). Excluded nested Sites/Vercel checkout metadata, raw recordings, local run evidence, caches, databases and all secret files. Kept final MP4/cover, code, tests, documentation and lockfiles. No history rewrite is planned; earlier commits still contain previously tracked legacy files.

README now leads with the real Groq recording and provides first-clone setup. Both LinkedIn drafts now share the repository; deployment-readiness.md lists exact hosted-release gaps. Extended redacted source scanner to Groq/GitHub fine-grained token patterns and JavaScript/JSON/config sources, still excluding .env and runtime data. CI container readiness now retries boundedly and cleans up on failure.

Fresh local verification: pytest 49 passed, 2 skipped (Ollama live opt-in and PostgreSQL opt-in); Ruff check/format passed; mypy 20 files passed; frontend build/lint and 9 component tests passed. Limited working-tree scanner: zero matches; not a complete Git-history audit. Docker daemon unavailable (dockerDesktopLinuxEngine pipe missing), so final local container/PostgreSQL checks did not run. Prior real Groq recording and browser checks remain the relevant live/UI evidence.

This is a working local development release, not a completed hosted multi-user product. Hosted identity/TLS, PostgreSQL restore, account usage budgets/shared limiting, parser resource limits and deployment-specific end-to-end checks remain outstanding. Public full AI deployment has not been attempted. GitHub push and CI results will be recorded after execution.


### Published release and remote verification

Pushed commit `3e9dedc9a628411cc96ce35cc642eb5dc99b993f` to origin/main with a normal fast-forward push. Repository: https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE . Published README fetched successfully and links the real Groq MP4. The local branch remains codex/failure-forensics-v2; user environment/data remain on disk. No force push or Git history rewrite.

GitHub Actions run https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/actions/runs/40260664727 completed successfully in all four jobs: backend (including the configured disposable PostgreSQL queue test), frontend (build/lint/components/audit), container (build, migration and readiness), and browser (end-to-end workflows). These remote checks resolve final-tree container build/readiness and PostgreSQL queue validation previously blocked by local Docker. They do not establish PostgreSQL restore, hosted authentication, production resource limits or real-model accuracy. Live Groq evidence remains the separately recorded run. Follow-up commit only updates documentation with these results and does not change runtime code.
