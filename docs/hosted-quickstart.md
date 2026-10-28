# Use your hosted workspace

Open https://failure-forensics-project.onrender.com . Free Render hosting can take a minute or more to wake after inactivity; leave the loading page open.

## Sign in and investigate

1. Find your generated password in `data/hosted-owner-password.txt` in your local project. This file is ignored by Git. Keep it private.
2. Sign in, then select **New investigation**.
3. Start with the invented invoice or a non-sensitive document. With Groq selected, submission sends redacted source text and outputs to Groq. Automatic redaction does not remove every private detail.
4. Keep the page open while extraction, classification and summarization run. Open each step to compare its output with the source.
5. Treat **succeeded** as execution status. An **inconclusive** quality finding means evidence or judging was insufficient; it does not mean the output is correct.
6. Use **Download investigation** to save the run and review history as JSON. These exports are evidence records, not full database backups or automatically importable restores.
7. Sign out when finished.

The recorded hosted test is run `8c102c6b-a411-4138-9b92-9c107ca0b7ab`. Its three Groq generation steps succeeded. Extraction and classification were assessed; the summary judge was unavailable, so quality remained inconclusive.

## Project hosting limits

- This is a private, single-owner workspace. Share the repository and video publicly; do not share its password as a public demo login.
- Free web hosting sleeps after inactivity, and the worker sleeps with it. PostgreSQL preserves queued jobs and results across web restarts.
- The current free database expires **25 November 2026**. Export important results before then. The local application remains available for continued use.
- No paid compute was provisioned. Workspace usage limits and Groq account limits still apply.
- Set or replace the Groq key directly in Render's service Environment page as `FF_GROQ_API_KEY`, then deploy the saved configuration. Never commit the key or put it in a frontend setting.

See [deployment readiness](deployment-readiness.md) for the verified checks and remaining operational limitations.
