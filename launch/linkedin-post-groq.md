# LinkedIn post — use with the real Groq demo

An AI pipeline can run successfully—and still produce the wrong answer.

The harder question is: where did the mistake begin, and which later outputs inherited it?

Over the past month, I’ve been building Failure Forensics from scratch to make that investigation visible.

It turns a document-processing pipeline—extraction, classification and summarization—into an inspectable chain of evidence. You can compare every output with its source, follow dependencies, review a suspected failure and test a correction without overwriting the original run.

🔍 Why this matters

A wrong invoice amount, missed contract detail or unsupported summary can look convincing after passing through several AI steps. Failure Forensics brings the source, intermediate outputs and evaluation findings into one workspace, helping developers investigate the starting point instead of repeatedly patching the final answer.

🧠 The AI engineering behind it

• Structured LLM outputs validated against explicit schemas.
• LLM-as-judge evaluation that separates source correctness from faithfulness to upstream inputs.
• Exact quote and character-offset checks to reject unsupported citations.
• Dependency-graph analysis to distinguish suspected origins from downstream symptoms.
• Controlled correction replays to test how a changed intermediate output affects later steps.
• Human review and versioned evaluation datasets for reproducible comparisons.

One result from the attached real-Groq demo captures the idea: the model extracted the correct invoice amount, but its evaluator returned citations that failed validation. The app kept the assessment inconclusive. A confident evaluator should not get the last word without evidence.

⚙️ Built end to end

AI & evaluation: Python · Groq inference · Ollama integration · Pydantic contracts
Backend & data: FastAPI · SQLAlchemy · PostgreSQL · Alembic · durable job processing
Interface: React · TypeScript · interactive pipeline graph · evidence comparison
Delivery & quality: Docker · GitHub Actions · Playwright · pytest · free Render hosting

The full app now has a private hosted workspace. The repository includes local setup so you can try it with your own Groq key. This is an AI engineering project focused on observability and evaluation; the demo is not a model-accuracy benchmark.

🎥 Real AI walkthrough attached.
💻 Code and setup: https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE

This is one of the projects I’ve been working on, and I’ll be sharing more of the remaining projects soon.

When an AI answer looks plausible, what evidence would you want before trusting it?

#AIEngineering #LLMEvaluation #ExplainableAI #MachineLearning #BuildInPublic
