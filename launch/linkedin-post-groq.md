# LinkedIn post — real Groq walkthrough version

Three AI steps completed successfully. The evidence review still said: **inconclusive**.

That is exactly the kind of distinction I wanted to make visible in **Failure Forensics**, which I built from scratch over the past month—not as an upgrade to an existing product.

I ran an invented invoice through the live Groq-powered app. Extraction, classification and summarization finished. The summary had the right invoice facts, but its cited character offsets did not line up with the source. The evaluator rejected the citations, and the app withheld a root-cause claim rather than treating a plausible answer as proof.

Failure Forensics helps developers follow a document through extraction → classification → summarization, inspect each result beside its evidence, and trace which upstream inputs each step used. Reviewers can record a judgment and replay downstream work after a correction while preserving the original run.

**AI/ML:** Groq inference · Ollama integration · structured outputs with Pydantic · LLM-as-judge · source-faithfulness checks · citation validation

**Application:** Python · FastAPI · SQLAlchemy · PostgreSQL · Alembic · React · TypeScript · interactive dependency graph

**Engineering:** durable background jobs · Docker · pytest · Playwright · GitHub Actions

🌐 **Try the public app:** https://failure-forensics-pk.vercel.app
No login or personal API key needed. Shared fair-use limits apply; use the invented sample or non-sensitive text.

🎥 **See the 43-second walkthrough:** https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/blob/main/launch/failure-forensics-public-demo.mp4

💻 **Repository:** https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE

This is one of several projects I’ve made. I’ll post about a few more soon. One live example shows a failure mode; it is not a model benchmark or a claim of measured accuracy improvement.

#AIEngineering #MachineLearning #LLMEvaluation #ResponsibleAI #MLOps #BuildInPublic
