# LinkedIn post — public demo version

Can an AI pipeline be wrong even when every step reports “succeeded”?

For the past month, I’ve been building **Failure Forensics from scratch**—a tool for investigating how a document’s evidence flows through AI processing, and where a result stops being trustworthy.

It traces a document through extraction, classification and summarization, then lets you inspect each output against its source and the steps it depends on.

**Why that matters:** in a live Groq-backed demo, all three generation steps succeeded and the summary captured the invoice facts. The evaluator then returned citation offsets that did not match the source text. Citation validation rejected that evidence, so the diagnosis stayed **inconclusive** instead of presenting an unsupported root cause as fact.

The goal is to make AI pipeline failures easier to investigate: distinguish execution from quality, see suspected origins separately from downstream symptoms, and keep uncertainty visible until a human has enough evidence.

**AI/ML work in the project**

• Schema-validated structured LLM outputs
• LLM-as-judge checks for source correctness and upstream faithfulness
• Exact quote and character-offset validation for citations
• Dependency-graph tracing across pipeline steps
• Human review, correction replay, and versioned evaluation datasets

**Tech stack**

AI & evaluation: Groq inference · Ollama integration · Python · Pydantic
Backend & data: FastAPI · SQLAlchemy · PostgreSQL · Alembic · durable job processing
Frontend: React · TypeScript · interactive evidence and dependency graph
Quality & delivery: pytest · Playwright · Docker · GitHub Actions

🌐 **Try the public app:** https://failure-forensics-pk.vercel.app
No sign-in is required. The demo has shared fair-use limits; please use the invented sample or other non-sensitive text.

🎥 **Watch the walkthrough:** https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/blob/main/launch/failure-forensics-public-demo.mp4

💻 **Source code:** https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE

This is one of the projects I’ve made. I’ll be sharing a few more of my projects in upcoming posts. This is an engineering demo, not a model-accuracy benchmark.

#AIEngineering #MachineLearning #LLMEvaluation #MLOps #ExplainableAI #BuildInPublic
