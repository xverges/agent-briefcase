"""Check that version references stay consistent across pyproject.toml and README.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"(.+?)"', text, re.MULTILINE)
    assert match, "version not found in pyproject.toml"
    return match.group(1)


def _readme_rev() -> str:
    text = (ROOT / "README.md").read_text()
    match = re.search(r"^\s+rev:\s*v(.+)$", text, re.MULTILINE)
    assert match, "rev: v... not found in README.md"
    return match.group(1)


def test_readme_rev_matches_pyproject_version():
    version = _pyproject_version()
    rev = _readme_rev()
    assert rev == version, (
        f"README.md rev (v{rev}) does not match pyproject.toml version ({version}). "
        f"Update the rev: in README.md to v{version}."
    )
