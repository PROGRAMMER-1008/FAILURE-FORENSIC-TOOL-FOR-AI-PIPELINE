# Contributing

Use Python 3.12.10 and Node 22.22.2. Install locked dependencies and run checks from README.
Tests default to fake inference; no model calls on import. Network-dependent PostgreSQL/browser checks are explicit; real-model tests need opt-in and a budget.

Never commit .env, uploads, private traces, database files, model artifacts or virtual environments.
Use invented fixtures and redact diagnostics. Preserve historical reviews/dataset versions. Describe measured evidence and limitations in changes.

No repository license was found during baseline inspection. The owner must choose licensing before redistribution; this implementation does not grant or select a license.
