"""Conservative redacted working-tree scanner. Never opens .env or data files.

Reports path/category only, not matching text. Not a credential/history audit.
"""

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential-token": re.compile(
        r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|gsk_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})"
    ),
    "assigned-secret": re.compile(
        r"""(?i)(?:api_key|password|access_token)\s*=\s*["'][A-Za-z0-9_+/=-]{24,}["']"""
    ),
}


def scan(root: Path) -> list[tuple[str, str]]:
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode()
        .split("\0")
    )
    findings = []
    for name in paths:
        path = Path(name)
        if not name or any(p.startswith(".env") for p in path.parts):
            continue
        if path.parts[0] in {"forensic", "data", ".venv", ".uv-cache"}:
            continue
        target = root / path
        if not target.is_file() or target.suffix not in {
            ".py",
            ".md",
            ".toml",
            ".yml",
            ".ts",
            ".tsx",
            ".js",
            ".mjs",
            ".json",
            ".yaml",
            ".cfg",
            ".ini",
        }:
            continue
        content = target.read_text(encoding="utf-8", errors="replace")
        for category, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append((name, category))
    return findings


if __name__ == "__main__":
    findings = scan(Path.cwd())
    for path, category in findings:
        print(f"{path}: {category} [REDACTED]")
    print(f"Working-tree findings: {len(findings)}; .env/data excluded; history not scanned.")
    raise SystemExit(bool(findings))
