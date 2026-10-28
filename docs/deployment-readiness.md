# Full-service deployment readiness

As of 26 October 2026, the local app and real Groq workflow work. The repository now includes a protected single-owner hosted application and a validated Render Blueprint. The free Render deployment reached live at https://failure-forensics-project.onrender.com on 26 October with owner sign-in and a configured Groq key. On 28 October, three readiness requests timed out; current availability and exact export persistence could not be reverified.

## Implemented and locally verified

- Single-owner login with password hashing, server-side session storage, expiry, logout/password-rotation revocation, origin checks and shared brute-force limiting. Browser test uses real HTTPS and verifies old-session rejection.
- Shared database-backed mutation and Groq request budgets, with bounded completion tokens. Limits persist across API/worker restarts; they are not a monetary spending guarantee.
- Linux parser CPU/address-space limits and per-process parser concurrency control, plus existing input-size and wall-time limits.
- Render web/worker/database configuration, explicit migration, worker startup gating, private database network and secret inputs. Official Render Blueprint schema check passed.
- Backend, frontend and type/lint checks are recorded in implementation-status.md. GitHub CI for commit 66a831c passed PostgreSQL restore/comparison, concurrent budgets, Linux parser limits, container readiness and HTTPS browser tests.

## Deployment verification and remaining limits

1. Completed: free combined web/worker service and free PostgreSQL in My Workspace. No paid provisioning is authorized. The database expires 25 November 2026; this is temporary project hosting.
2. Completed: repository connected, owner password hash configured, and user-entered Groq key deployed. Authenticated live invoice completed all three producer steps using Groq; export and logout passed. The summary judge returned unavailable, so overall quality remains inconclusive.
3. Remaining: the exact export comparison after restart did not run because live readiness timed out on three bounded attempts on 28 October. The earlier browser check displayed the saved run after redeploy, but this is not an exact export comparison. No target-host database restore or alert-delivery test has been performed. Free PostgreSQL offers no managed backup; export important investigations and choose a lasting storage destination before expiry. CI backup/restore evidence applies to its disposable PostgreSQL, not to this account.

Use [the Render deployment guide](render-deployment.md). The current product is a private owner workspace, not a public multi-tenant SaaS. Do not share the owner password with visitors. The optional legacy OIDC proxy integration is not required by built-in hosted mode and remains an independently configured path.

Independent human agreement and real-model accuracy studies remain research work; no benchmark result is inferred from the synthetic tests or one real Groq example.

Latest application commit `39007aa`: all four GitHub Actions jobs passed (backend, frontend, container, browser), run https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/actions/runs/40353424554 .
