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

# Characters that are invisible and can carry hidden instructions (prompt injection).
# Covers: C0 control chars, soft hyphen, zero-width chars, Unicode bidi controls/isolates,
# BOM, and the Unicode tag block (U+E0000-U+E007F).
_INVISIBLE_RE = re.compile(
    "["
    "\x01-\x08"  # C0 control (not tab \x09, LF \x0a, CR \x0d)
    "\x0b\x0c"  # vertical tab, form feed
    "\x0e-\x1f"  # remaining C0 control chars
    "\u00ad"  # soft hyphen
    "\u200b-\u200d"  # zero-width space / non-joiner / joiner
    "\u202a-\u202e"  # Unicode bidi controls (LRE, RLE, PDF, LRO, RLO)
    "\u2066-\u2069"  # Unicode bidi isolates (LRI, RLI, FSI, PDI)
    "\ufeff"  # BOM / zero-width no-break space
    "\U000e0000-\U000e007f"  # Unicode tag block
    "]"
)

_CHAR_NAMES: dict[int, str] = {
    0x00AD: "soft hyphen",
    0x200B: "zero-width space",
    0x200C: "zero-width non-joiner",
    0x200D: "zero-width joiner",
    0xFEFF: "byte order mark / zero-width no-break space",
}


def _char_description(ch: str) -> str:
    cp = ord(ch)
    if cp in _CHAR_NAMES:
        return f"{_CHAR_NAMES[cp]} (U+{cp:04X})"
    if 0x202A <= cp <= 0x202E:
        return f"bidi control character (U+{cp:04X})"
    if 0x2066 <= cp <= 0x2069:
        return f"bidi isolate character (U+{cp:04X})"
    if 0xE0000 <= cp <= 0xE007F:
        return f"Unicode tag character (U+{cp:04X})"
    return f"control character (U+{cp:04X})"


def check_invisible_chars(content: str, label: str) -> list[str]:
    """Return finding messages for invisible/suspicious characters in content."""
    findings = []
    for line_no, line in enumerate(content.splitlines(keepends=True), 1):
        for match in _INVISIBLE_RE.finditer(line):
            col = match.start() + 1
            findings.append(f"  {label}:{line_no}:{col}: {_char_description(match.group())}")
    return findings


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

    # Scan all config-src/ files for invisible characters before building.
    # These can carry hidden instructions invisible to human reviewers (prompt injection).
    all_findings: list[str] = []
    for path in sorted(src_root.rglob("*")):
        if path.is_file():
            label = str(path.relative_to(briefcase_dir))
            all_findings.extend(check_invisible_chars(path.read_text(), label))
    if all_findings:
        raise ValueError(
            "invisible/suspicious characters found in config-src/ files"
            " (possible prompt injection):\n" + "\n".join(all_findings)
        )

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
