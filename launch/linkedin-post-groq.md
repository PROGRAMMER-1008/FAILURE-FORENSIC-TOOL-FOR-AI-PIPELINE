# LinkedIn post — real AI video

For the past month, I’ve been building Failure Forensics from scratch: a tool to understand what happens inside a document-processing AI pipeline.

The attached demo uses real Groq inference on an invented invoice. It extracts the facts, classifies the document, and generates a summary—with each step visible alongside the original evidence.

An interesting result from this run: the AI extracted the correct amount, 814 EUR, but its summary evaluator produced citations that failed validation. The app kept the assessment inconclusive instead of presenting it as verified.

That is the problem I wanted to explore: finishing a pipeline successfully is different from knowing its answer is correct.

I built an interactive dependency graph, source/output comparisons, human reviews, controlled correction replays, and versioned review datasets. The stack is React, TypeScript, FastAPI, SQLAlchemy and Alembic, with Groq and local Ollama adapters.

The video shows real AI responses. The repository includes setup instructions so you can run the full app locally with your own Groq key.

Explore the code and run it locally: https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE

Full hosted deployment is still in progress; this is a working local development release.

This is one of the projects I’ve been working on. I’ll be sharing more posts about the remaining projects soon.

What would help you investigate an AI pipeline when the final answer looks plausible but something feels wrong?

#AIEngineering #LLM #FullStackDevelopment #Python #BuildInPublic
