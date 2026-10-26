# Clean development setup

Install uv; Python is pinned to 3.12.10. Do not execute forensic/ binaries.

```powershell
uv sync --frozen
uv run --frozen pytest
uv run --frozen ruff check
uv run --frozen ruff format --check
uv run --frozen mypy
```

uv.lock pins transitive dependencies. Tests collect only tests/ and disable sockets.
Legacy demonstrations move to examples/ and run explicitly with `python -m examples.<name>`.
They may use Ollama/private data and are not automated regression evidence.
