#!/usr/bin/env python3
"""Fail on release hygiene, secret, or synthetic-fixture provenance problems."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = {
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
}
FORBIDDEN_NAMES = {".DS_Store", ".env", "private_api_env.sh"}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    listed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    release_paths = sorted(Path(item.decode("utf-8")) for item in listed.split(b"\0") if item)
    for rel in release_paths:
        path = root / rel
        if not path.is_file():
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix == ".pyc":
            failures.append(f"forbidden generated/private file: {rel}")
            continue
        if path.stat().st_size > 5_000_000 or path.suffix.lower() in {".png", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"possible {label}: {rel}")
        if "legacy" not in rel.parts and re.search(r"/(?:data/peizhengqi|home/[^/]+/)", text):
            failures.append(f"canonical file contains a server-local absolute path: {rel}")

    license_path = root / "examples" / "toy" / "DATA_LICENSE.json"
    if not license_path.exists():
        failures.append("missing examples/toy/DATA_LICENSE.json")
    else:
        data = json.loads(license_path.read_text(encoding="utf-8"))
        if data.get("synthetic") is not True or data.get("license") != "CC0-1.0":
            failures.append("toy data must be marked synthetic under CC0-1.0")
        for name in data.get("files", []):
            if not (license_path.parent / name).is_file():
                failures.append(f"toy license manifest references missing file: {name}")

    if failures:
        print("Release hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Release hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
