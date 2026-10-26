# Full-service deployment readiness

As of 26 October 2026, the local application and a real Groq workflow work. The complete hosted service is **not yet release-ready**. Share the repository and real AI video while the remaining deployment checks are completed.

## Verified

- Durable API/worker processing, tracing, human review, controlled replay and dataset mechanics have automated local coverage.
- Local Groq producer calls completed extraction, classification and summarization on an invented invoice. Invalid evaluator citations were rejected and quality stayed inconclusive.
- Frontend production build, component tests and browser evidence are documented in implementation-status.md.
- GitHub CI passed for release commit `3e9dedc`: backend with PostgreSQL queue validation, frontend, container build/migration/readiness, and browser workflows. Existing sample websites are not the full backend.

## Required before a hosted release

1. Complete a PostgreSQL backup-restore drill and restart/rollback checks on the intended host. GitHub CI has now passed final-tree container build/readiness and PostgreSQL queue tests; local Docker remains unavailable.
2. Select an API/long-running-worker host and private persistent PostgreSQL service. The Vercel static site alone does not host this architecture. No paid infrastructure has been authorized.
3. Configure and test TLS and the trusted OIDC proxy with a real account. Current private mode is single-owner; public multi-user workspaces and per-user data isolation are not implemented.
4. Enforce account usage budgets and shared rate limits before allowing visitors to consume the owner's Groq quota. Current mutation limits are process-local.
5. Validate resource limits for uploads/parsers, private backups, restore, secret injection, monitoring and rollback on the selected host.
6. Run authenticated end-to-end checks, including session expiry, identity-header spoofing, tenant/workspace boundaries as applicable, cancellation and restart recovery.

A private single-owner deployment and a publicly usable multi-user product have different acceptance criteria. Do not bypass private-mode checks or put the Groq key into a browser bundle to make a public demo appear complete.

Real model accuracy, judge independence and human agreement also remain unmeasured; successful execution does not establish those claims.
