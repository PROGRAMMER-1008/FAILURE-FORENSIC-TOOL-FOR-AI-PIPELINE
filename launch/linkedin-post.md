# LinkedIn post — ready to copy

One wrong number can travel through an AI pipeline and come back as a confident answer.

But where did it first go wrong?

For the past month, I’ve been building **Failure Forensics** from scratch to explore that question.

It’s a tool for investigating document-processing pipelines: extract facts, classify the document, generate a summary—and make each step inspectable when something goes wrong.

In the demo, an invented invoice says **814 EUR**, but the extraction deliberately returns **999 EUR**. The summary repeats the mistake. Instead of only fixing the final answer, I can follow the dependencies, compare the source with the outputs, review the finding, and test a correction while preserving the original run.

What I built:

• An interactive pipeline graph with step-by-step evidence
• Separate execution status and content-quality findings
• Human reviews, including an explicit “unsure” option
• Controlled replays and original-versus-replay comparisons
• Versioned review datasets and synthetic evaluation checks
• Groq and local Ollama integrations in the full application

The stack: **React, TypeScript, FastAPI, SQLAlchemy and Alembic**, with a durable background worker.

One lesson I’m taking away: a pipeline finishing successfully doesn’t mean its answer is correct. And a suspected cause still needs evidence.

🎥 The attached video walks through the actual app using a synthetic example.
🔎 Explore the repository and local setup: https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE

The repository includes local setup with Groq. This synthetic video demonstrates mechanics, not real-model accuracy; a separate real Groq recording is also included. Full hosted deployment remains in progress.

This is one of the projects I’ve been working on. I’ll be sharing a few more posts about the remaining projects soon.

If you build AI pipelines, what would make a debugging tool like this more useful to you?

#AIEngineering #LLM #FullStackDevelopment #Python #BuildInPublic
