"""Conservative secret redaction; not comprehensive PII detection."""

import hashlib
import json
import re
from typing import Any

SECRET_KEY = re.compile(r"(?i)(authorization|password|secret|api[_-]?key|access[_-]?token)")
TOKEN = re.compile(
    r"(?i)(bearer\s+\S+|(?:sk-|ghp_)[A-Za-z0-9_-]{8,}|(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*[\"']?[^\s,\"'}]+)"
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SECRET_KEY.search(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return TOKEN.sub("[REDACTED]", value)
    return value


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
