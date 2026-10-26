# Failure Forensics launch kit

Recommended sharing link: https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE

Share the repository with `failure-forensics-groq-demo.mp4`. The earlier static demo is optional and is not the full application.

- `failure-forensics-demo.mp4`: captioned recording of the actual local app, H.264, 1280×800, silent. Uses invented data and the synthetic provider only.
- `failure-forensics-demo.webm`: original browser recording.
- `video-cover.png`: cover image from the recording.
- `demo-captions.srt`: optional timed captions for the 57.64-second silent video. Captions are also visible in the video.
- `demo-chapters.json`: chapter timing and caption text; reusable as a narration outline.
- `linkedin-post.md`: first-person post drafted from the owner's stated month-long project history. Describes a project built from scratch, not an upgrade.
- `public-demo-desktop.png` / `public-demo-mobile.png`: public showcase QA captures.
- `deployment.md`: verified deployment details, usage instructions and limits.

Upload the MP4 directly to LinkedIn, paste `linkedin-post-groq.md`, and use the repository link. Review the first-person wording before posting. No LinkedIn post or message has been sent on your behalf.

The public sample is intentionally separate from the private full application: no document uploads, API key entry, real AI requests or shared database. The full Python API and worker are not deployed by the static showcase. Visitor input in the correction exercise stays in browser memory and disappears on refresh.

## Reproduce the recording

Use a dedicated synthetic database, migrate it, and start the API/worker on loopback port 18767 with `FF_PROVIDER=fake`. From `frontend`, run `node scripts/record-demo.mjs` with Node 22.22.2. The script does not load .env. Convert the resulting WebM to MP4 using FFmpeg with H.264 and yuv420p. Never record private source documents or credential settings.

## Real Groq recording

`failure-forensics-groq-demo.mp4` is a second, 61.96-second captioned silent recording using live Groq (`openai/gpt-oss-20b`), an invented invoice and no error injection. The three generation steps completed. Extraction returned 814 EUR; classification returned invoice. The summary evaluator failed citation validation, so overall quality remained inconclusive. This is one observed run, not an accuracy benchmark.

Supporting files: `groq-run-evidence.json`, `groq-demo-chapters.json`, `groq-video-cover.png`, and the original WebM. The recording uses a separate database and the existing app's runtime credential loading; no key was displayed or copied into these artifacts. API requests use the owner's Groq account quota.

`vercel-sample/` is an isolated static deployment folder for a personal Vercel address. It does not expose the Groq backend. Published under the owner’s Vercel account at https://failure-forensics-pk.vercel.app.
