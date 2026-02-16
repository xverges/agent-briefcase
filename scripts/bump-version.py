#!/usr/bin/env python3
"""Bump the project version in pyproject.toml, README.md, and uv.lock.

Usage: python scripts/bump-version.py <new-version>
Example: python scripts/bump-version.py 0.12.0

Validate with: uv run pytest tests/test_version.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"(.+?)"', text, re.MULTILINE)
    if not match:
        sys.exit("Error: could not find version in pyproject.toml")
    return match.group(1)


def update_pyproject(old: str, new: str) -> None:
    path = ROOT / "pyproject.toml"
    text = path.read_text()
    updated = text.replace(f'version = "{old}"', f'version = "{new}"', 1)
    path.write_text(updated)
    print("  Updated pyproject.toml")


def update_readme(old: str, new: str) -> None:
    path = ROOT / "README.md"
    text = path.read_text()
    updated = text.replace(f"rev: v{old}", f"rev: v{new}")
    count = text.count(f"rev: v{old}")
    path.write_text(updated)
    print(f"  Updated README.md ({count} occurrence{'s' if count != 1 else ''})")


def update_uv_lock() -> None:
    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    print("  Updated uv.lock")


def fail(message: str) -> None:
    print(f"Current version: {read_current_version()}", file=sys.stderr)
    sys.exit(message)


def main() -> None:
    if len(sys.argv) != 2:
        fail(f"Usage: {sys.argv[0]} <new-version>  (e.g. 0.12.0)")

    new_version = sys.argv[1]
    if not re.fullmatch(r"\d+\.\d+\.\d+", new_version):
        fail("Error: version must be in X.Y.Z format")

    old_version = read_current_version()
    if old_version == new_version:
        fail(f"Version is already {new_version}")

    print(f"Bumping version: {old_version} -> {new_version}")
    update_pyproject(old_version, new_version)
    update_readme(old_version, new_version)
    update_uv_lock()

    print("\nDone. Validate with:\n  uv run pytest tests/test_version.py")


if __name__ == "__main__":
    main()
