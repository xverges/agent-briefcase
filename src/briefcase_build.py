"""agent-briefcase: build config/ from config-src/ templates with include expansion."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CONFIG_SRC = "config-src"
CONFIG_OUT = "config"
INCLUDES_DIR = "_includes"
INCLUDE_RE = re.compile(r"^\{\{include\s+(.+?)\}\}[ \t]*$", re.MULTILINE)


def resolve_includes(content: str, includes_dir: Path, *, _chain: tuple[str, ...] = ()) -> str:
    """Replace {{include <file>}} directives with fragment contents.

    Raises on circular or missing includes.
    """

    def replacer(match: re.Match) -> str:
        filename = match.group(1).strip()
        if filename in _chain:
            cycle = " → ".join([*_chain, filename])
            raise ValueError(f"circular include detected: {cycle}")
        fragment = includes_dir / filename
        if not fragment.is_file():
            raise FileNotFoundError(f"include file not found: {filename}")
        fragment_content = fragment.read_text()
        return resolve_includes(fragment_content, includes_dir, _chain=(*_chain, filename))

    return INCLUDE_RE.sub(replacer, content)


def build(briefcase_dir: Path) -> int:
    """Build config/ from config-src/. Returns 0 if unchanged, 1 if files were written/removed."""
    src_root = briefcase_dir / CONFIG_SRC
    out_root = briefcase_dir / CONFIG_OUT
    includes_dir = src_root / INCLUDES_DIR

    if not src_root.is_dir():
        print("briefcase-build: no config-src/ directory, nothing to build.")
        return 0

    # Collect source files (excluding _includes/)
    src_files: dict[str, Path] = {}
    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_root)
        # Skip anything under _includes/
        if rel.parts[0] == INCLUDES_DIR:
            continue
        src_files[str(rel)] = path

    # Process each source file
    changed = False
    written_paths: set[str] = set()

    for rel_str, src_path in sorted(src_files.items()):
        dest = out_root / rel_str
        written_paths.add(rel_str)

        content = src_path.read_text()
        resolved = resolve_includes(content, includes_dir)

        existed = dest.is_file()
        if existed and dest.read_text() == resolved:
            print(f"  unchanged: {rel_str}")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(resolved)
        print(f"  {'updated' if existed else 'created'}: {rel_str}")
        changed = True

    # Remove stale files from config/ that no longer have a source in config-src/
    if out_root.is_dir():
        for path in sorted(out_root.rglob("*")):
            if not path.is_file():
                continue
            rel_str = str(path.relative_to(out_root))
            if rel_str not in written_paths:
                path.unlink()
                print(f"  removed: {rel_str}")
                changed = True
                # Clean up empty parent directories
                parent = path.parent
                while parent != out_root:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent

    if changed:
        return 1

    # Config on disk is up-to-date. Check whether any config/ files need staging.
    unstaged = check_unstaged_config(briefcase_dir)
    if unstaged:
        print("briefcase-build: config/ files need to be staged:")
        for f in sorted(unstaged):
            print(f"  unstaged: {f}")
        return 1

    return 0


def check_unstaged_config(briefcase_dir: Path) -> list[str]:
    """Return config/ files that have unstaged changes (modified or untracked).

    Returns an empty list if not inside a git repo.
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=briefcase_dir,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    # Modified but not staged
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", CONFIG_OUT],
        cwd=briefcase_dir,
        capture_output=True,
        text=True,
    )
    unstaged = {f for f in result.stdout.splitlines() if f}

    # Untracked files under config/
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", CONFIG_OUT],
        cwd=briefcase_dir,
        capture_output=True,
        text=True,
    )
    unstaged |= {f for f in result.stdout.splitlines() if f}

    return sorted(unstaged)


def main(argv: list[str] | None = None) -> int:
    """Entry point for briefcase-build command."""
    # Build runs in the briefcase repo itself (cwd)
    briefcase_dir = Path.cwd()
    return build(briefcase_dir)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
