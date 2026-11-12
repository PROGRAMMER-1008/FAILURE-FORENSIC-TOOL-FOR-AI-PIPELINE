# Full-service deployment readiness

## Current public demo — 12 November 2026

1. **Completed:** the public React app is live at https://failure-forensics-pk.vercel.app through Vercel, with its API routed to the existing free Render service. No visitor password or personal Groq key is required.
2. **Completed:** a live anonymous invoice run used Groq for extraction, classification and summarization. Citation offsets failed source validation, so the diagnosis remained inconclusive. This validates one workflow, not model accuracy.
3. **Remaining:** restart/export persistence has not been compared against the live database. No target-host restore or alert-delivery test has been performed. Free PostgreSQL expires 25 November 2026; export important investigations and choose durable storage before then. CI restore evidence is from disposable PostgreSQL, not this account.

Use [the Render deployment guide](render-deployment.md) for the separate owner-only configuration and [the public deployment guide](public-deployment.md) for visitor mode. The older owner-only URL is not the public app. The optional legacy OIDC proxy integration remains a separate path.

Independent human agreement and real-model accuracy studies remain research work; no benchmark result is inferred from the synthetic tests or one real Groq example.

Latest application commit `42f9f87`: all four GitHub Actions jobs passed (backend, frontend, container, browser), run https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/actions/runs/40737632217 .

## Historical owner deployment record — 26 October 2026

The original free Render deployment used owner sign-in and a configured Groq key. It is not the public visitor URL. Earlier readiness checks recorded a timeout for a post-restart export comparison; that historical limitation is still relevant to the older owner workflow but does not negate the later public-run verification above.

The free PostgreSQL database expires 25 November 2026. Free hosting sleeps when idle. No paid resources were provisioned.
