"""No inference: report local Ollama reachability/model names, never config values."""

import json
import urllib.request


if __name__ == "__main__":
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            data = json.load(response)
        print(
            json.dumps(
                {
                    "ollama_reachable": True,
                    "models": [m.get("name") for m in data.get("models", [])],
                }
            )
        )
    except Exception as exc:
        print(
            json.dumps(
                {"ollama_reachable": False, "reason": type(exc).__name__, "inference": "not_run"}
            )
        )
