"""agent-briefcase: scaffold a new briefcase repo."""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path

# ---------------------------------------------------------------------------
# Generated file contents
# ---------------------------------------------------------------------------

BRIEFCASE_MD = """\
# Team Briefcase

This repo holds your team's shared AI agent configuration. It is managed by
[agent-briefcase](https://github.com/xverges/agent-briefcase).

## Directory structure

| Directory | Purpose |
|---|---|
| `config-src/_shared/` | Configuration that syncs to **all** target repos. |
| `config-src/<project>/` | Configuration that syncs only to the matching repo. |
| `config-src/_includes/` | Reusable fragments referenced by `{{{{include <file>}}}}` directives. |
| `config/` | **Generated** — do not edit directly. Built from `config-src/` on every commit. |
| `dotfiles/` | A place to share personal dotfiles with the team. Not managed by briefcase. |

## Editing configuration

1. Edit files under `config-src/`.
2. Use `{{{{include <file>}}}}` to pull in fragments from `_includes/`.
3. Preview the result with `pre-commit run briefcase-build --all-files`.
4. Commit — the `briefcase-build` pre-commit hook assembles `config/` automatically.

## Adding the sync hook to a target repo

In the target repo's `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [post-checkout, post-merge]
repos:
  - repo: https://github.com/xverges/agent-briefcase
    rev: {version}
    hooks:
      - id: briefcase-sync
        args: [--briefcase=../{dir_name}]
```

Then run `pre-commit install`.
"""

INCLUDES_README = """\
# _includes

Place reusable fragments here. Reference them from any template with:

```
{{include filename.md}}
```

The directive must be on its own line. Fragments can include other fragments.
"""

DOTFILES_README = """\
# dotfiles

A place for team members to share personal configuration files — shell aliases,
editor settings, tool configs, etc.

These files are **not** managed by briefcase. They are not synced or built.
They live here as a convenience so the team can learn from each other's setups.
"""


def _get_version() -> str:
    try:
        return "v" + version("agent-briefcase")
    except Exception:
        return "vX.Y.Z"


def _scaffold_files(dir_name: str) -> dict[str, str]:
    return {
        "BRIEFCASE.md": BRIEFCASE_MD.format(version=_get_version(), dir_name=dir_name),
        "config-src/_includes/README.md": INCLUDES_README,
        "dotfiles/README.md": DOTFILES_README,
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
