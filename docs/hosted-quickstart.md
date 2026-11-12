# Use the public Failure Forensics app

Open [https://failure-forensics-pk.vercel.app](https://failure-forensics-pk.vercel.app). No sign-up, password or personal Groq key is required. The owner supplies the Groq connection; Vercel serves the interface and forwards API requests to Render.

## Run the invented invoice

1. Choose **New investigation**.
2. Select **Load invented invoice**, then **Queue investigation**.
3. Watch extraction, classification and summarization finish. Free hosting may take a minute to wake.
4. Follow the dependency graph. Select a step to compare its output with the source and inspect evaluator evidence.
5. Treat execution status and quality assessment separately. An inconclusive result means the evidence was insufficient or invalid; it is not a pass.
6. Use **Download investigation** to save the run and review history before leaving.

The visitor session is stored in a browser cookie and lasts 24 hours. It is not an account: clearing cookies, switching browsers or waiting for expiry loses access. Visitor histories are isolated from other visitors and the original owner workspace.

## Privacy and shared limits

Use the invented sample or other non-sensitive text. The app attempts secret redaction, then sends document text and intermediate outputs to Groq for generation and evaluation. Redaction can miss private details. Do not submit personal, confidential or customer documents.

The public deployment allows up to 3 submission attempts per visitor and 20 shared submissions per UTC day; its shared Groq-call budget is 100 per day. Failed attempts can use these allowances. Free Render hosting sleeps when idle, and the current free project database expires on **25 November 2026**. Download results you want to keep. Availability after that date is not promised.

See [public deployment and limits](public-deployment.md) and the [live deployment verification record](deployment-readiness.md). The private owner-only Render URL is not the public app.
