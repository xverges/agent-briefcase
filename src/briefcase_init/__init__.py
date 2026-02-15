"""agent-briefcase: scaffold a new briefcase repo."""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(name: str, **replacements: str) -> str:
    """Load a template file, optionally substituting placeholders."""
    content = (_TEMPLATES_DIR / name).read_text()
    for key, value in replacements.items():
        content = content.replace(key, value)
    return content


def _get_version() -> str:
    try:
        return "v" + version("agent-briefcase")
    except Exception:
        return "vX.Y.Z"


def _scaffold_files(dir_name: str) -> dict[str, str]:
    v = _get_version()
    return {
        "BRIEFCASE.md": _load_template("BRIEFCASE.md.template", **{"$VERSION": v, "$DIR_NAME": dir_name}),
        "config-src/_includes/README.md": _load_template("includes-README.md"),
        "dotfiles/README.md": _load_template("dotfiles-README.md"),
    }


# ---------------------------------------------------------------------------
# Init logic
# ---------------------------------------------------------------------------


def init(target_dir: Path) -> int:
    """Scaffold the briefcase directory structure. Skips existing files."""
    dir_name = target_dir.resolve().name
    files = _scaffold_files(dir_name)
    created: list[str] = []
    skipped: list[str] = []

    # Ensure empty directories exist
    for dir_path in ["config", "config-src/_shared"]:
        d = target_dir / dir_path
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            print(f"  created: {dir_path}/")

    for rel_path, content in sorted(files.items()):
        dest = target_dir / rel_path
        if dest.exists():
            skipped.append(rel_path)
            print(f"  skipped: {rel_path} (already exists)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        created.append(rel_path)
        print(f"  created: {rel_path}")

    if not created:
        print("briefcase-init: everything already exists, nothing to do.")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for briefcase-init command."""
    return init(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
