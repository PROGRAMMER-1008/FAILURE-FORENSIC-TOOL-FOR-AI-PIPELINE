"""
Single wrapper around the Ollama API.

WHY THIS FILE MATTERS:
Every pipeline step needs to call an LLM. Instead of each step writing
its own HTTP/ollama call, they all go through this one function. That
means:
  1. If we ever swap models, we change ONE place.
  2. We can log every single LLM call in one location (useful later
     for the tracing layer).
  3. We enforce structured JSON output consistently everywhere.

This module assumes Ollama is running locally at http://localhost:11434
(the default). It does NOT run inside this sandbox - you will run this
on your own laptop where Ollama is installed.
"""

import ollama
import json
import time
from dataclasses import dataclass


DEFAULT_MODEL = "llama3.1:8b"


@dataclass
class LLMCallResult:
    """Everything worth knowing about one LLM call."""
    raw_response: str
    parsed_json: dict | None
    latency_seconds: float
    model: str
    success: bool
    error: str | None = None


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
) -> LLMCallResult:
    """
    Calls the local Ollama model and expects a JSON object back.

    We ask the model to respond in JSON, then try to parse it. LLMs
    sometimes wrap JSON in markdown code fences (```json ... ```) or
    add stray text before/after - we strip that defensively rather
    than assuming a perfectly clean response.
    """
    start = time.time()
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format="json",  # Ollama's structured-output mode: constrains output to valid JSON
            options={"temperature": 0.1},  # low temperature = more consistent, less creative
        )
        raw_text = response["message"]["content"]
        latency = time.time() - start

        cleaned = _strip_code_fences(raw_text)
        parsed = json.loads(cleaned)

        return LLMCallResult(
            raw_response=raw_text,
            parsed_json=parsed,
            latency_seconds=latency,
            model=model,
            success=True,
        )

    except json.JSONDecodeError as e:
        return LLMCallResult(
            raw_response=raw_text if "raw_text" in dir() else "",
            parsed_json=None,
            latency_seconds=time.time() - start,
            model=model,
            success=False,
            error=f"JSON parse failed: {e}",
        )
    except Exception as e:
        return LLMCallResult(
            raw_response="",
            parsed_json=None,
            latency_seconds=time.time() - start,
            model=model,
            success=False,
            error=f"LLM call failed: {e}",
        )


def _strip_code_fences(text: str) -> str:
    """Removes ```json ... ``` wrapping if the model added it despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop first ``` line
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # drop last ``` line
        text = "\n".join(lines)
    return text.strip()
