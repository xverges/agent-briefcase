"""Check that version references stay consistent across pyproject.toml.

Scans all project files for ``rev: vX.Y.Z`` patterns and ensures they match
the version declared in pyproject.toml.  Files that use placeholders (like
``$VERSION`` or ``v<VERSION>``) are intentionally excluded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".nox", ".venv", ".git", "node_modules", "__pycache__"}
SKIP_FILES = {
    ".pre-commit-config.yaml",  # references third-party hooks, not our version
}
# Auto-generated from approved files; the source of truth is the approved file.
SKIP_PREFIXES = ("SCENARIOS-",)

REV_RE = re.compile(r"rev:\s*v(\d+\.\d+\.\d+)")


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"(.+?)"', text, re.MULTILINE)
    assert match, "version not found in pyproject.toml"
    return match.group(1)


def _find_rev_references() -> list[tuple[str, int, str]]:
    """Return (relative_path, line_number, found_version) for every rev: vX.Y.Z."""
    hits: list[tuple[str, int, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml", ".txt", ".toml"}:
            continue
        if path.name in SKIP_FILES or any(path.name.startswith(p) for p in SKIP_PREFIXES):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = REV_RE.search(line)
            if m:
                hits.append((str(path.relative_to(ROOT)), lineno, m.group(1)))
    return hits


def test_all_rev_references_match_pyproject_version():
    version = _pyproject_version()
    hits = _find_rev_references()
    assert hits, "No rev: vX.Y.Z references found — expected at least one in README.md"

    mismatches = [(f, ln, v) for f, ln, v in hits if v != version]
    if mismatches:
        details = "\n".join(f"  {f}:{ln}  has v{v}" for f, ln, v in mismatches)
        assert not mismatches, (
            f"Found rev: references that don't match pyproject.toml version ({version}):\n"
            f"{details}\n"
            f"Update them to v{version}."
        )
