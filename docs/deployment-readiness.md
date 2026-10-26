# Full-service deployment readiness

As of 26 October 2026, the local app and real Groq workflow work. The repository now includes a protected single-owner hosted application and a validated Render Blueprint. Actual Render deployment has not been performed.

## Implemented and locally verified

- Single-owner login with password hashing, server-side session storage, expiry, logout/password-rotation revocation, origin checks and shared brute-force limiting. Browser test uses real HTTPS and verifies old-session rejection.
- Shared database-backed mutation and Groq request budgets, with bounded completion tokens. Limits persist across API/worker restarts; they are not a monetary spending guarantee.
- Linux parser CPU/address-space limits and per-process parser concurrency control, plus existing input-size and wall-time limits.
- Render web/worker/database configuration, explicit migration, worker startup gating, private database network and secret inputs. Official Render Blueprint schema check passed.
- Backend, frontend and type/lint checks are recorded in implementation-status.md. CI now includes PostgreSQL restore/comparison, concurrent budgets, container readiness and HTTPS browser tests; see the latest verification log for results.

## Required external deployment steps

1. Authorize Render's paid persistent web/worker/database plans after reviewing the account quote. No paid resources have been created.
2. Connect the repository in the owner's Render account, enter the Groq key and generated owner-password hash directly in secret settings, and deploy the same tested commit to web and worker.
3. Verify the actual Render HTTPS origin, authenticated Groq run, restart recovery, new-database restore, retention, monitoring and alert recipients. CI cannot certify these account-specific operations.

Use [the Render deployment guide](render-deployment.md). The current product is a private owner workspace, not a public multi-tenant SaaS. Do not share the owner password with visitors. The optional legacy OIDC proxy integration is not required by built-in hosted mode and remains an independently configured path.

Independent human agreement and real-model accuracy studies remain research work; no benchmark result is inferred from the synthetic tests or one real Groq example.
