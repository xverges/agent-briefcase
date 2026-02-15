"""agent-briefcase: sync AI agent configuration files from a shared repo."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

LOCK_FILE = ".briefcase.lock"
POST_SYNC_HOOK = ".briefcase-post-sync.sh"
MARKER_BEGIN = "# BEGIN briefcase-managed (do not edit this section)"
MARKER_END = "# END briefcase-managed"
DEFAULT_BRIEFCASE_DIR_NAME = "team-briefcase"
CONFIG_DIR = "config"
DEFAULT_SHARED_FOLDER = "_shared"


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_lock(path: Path) -> dict:
    if not path.exists():
        return {"source_commit": "", "files": {}}
    with open(path) as f:
        return json.load(f)


def write_lock(path: Path, source_commit: str, files: dict[str, dict]) -> None:
    data = {"source_commit": source_commit, "files": files}
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def get_briefcase_commit(briefcase_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(briefcase_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def check_briefcase_staleness(briefcase_dir: Path) -> None:
    """Fetch the briefcase remote and warn if local HEAD is behind.

    This is purely informational — it never modifies the working tree.
    Failures (offline, not a git repo, no remote) are silently ignored.
    """
    git = ["git", "-C", str(briefcase_dir)]
    try:
        # Fetch remote tracking refs (non-destructive)
        subprocess.run(
            [*git, "fetch", "--quiet"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        # Get local HEAD
        local = subprocess.run(
            [*git, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        # Get the default remote branch (try origin/main, then origin/master)
        for branch in ("origin/main", "origin/master"):
            try:
                remote = subprocess.run(
                    [*git, "rev-parse", branch],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                break
            except subprocess.CalledProcessError:
                continue
        else:
            return  # no known remote branch found

        if local == remote:
            return

        # Count how many commits we're behind
        behind = subprocess.run(
            [*git, "rev-list", "--count", f"{local}..{remote}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        print(
            f"briefcase: WARNING — briefcase repo is {behind} commit(s) behind {branch}. "
            f"Run `git -C {briefcase_dir} pull` to get the latest team config.",
            file=sys.stderr,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass


def collect_files(briefcase_dir: Path, project_name: str, shared_folder: str) -> dict[str, Path]:
    """Collect files to sync with layering: shared/ then project-specific/.

    Returns {dest_relative_path: source_absolute_path}.
    Project-specific files override shared files at the same dest path.
    """
    files: dict[str, Path] = {}

    config_root = briefcase_dir / CONFIG_DIR

    shared_dir = config_root / shared_folder
    if shared_dir.is_dir():
        for src in sorted(shared_dir.rglob("*")):
            if src.is_file():
                rel = str(src.relative_to(shared_dir))
                files[rel] = src

    project_dir = config_root / project_name
    if project_dir.is_dir():
        for src in sorted(project_dir.rglob("*")):
            if src.is_file():
                rel = str(src.relative_to(project_dir))
                files[rel] = src

    return files


def sync_files(
    files_to_sync: dict[str, Path],
    old_lock: dict,
    briefcase_dir: Path,
) -> dict[str, dict]:
    """Sync files, skipping locally modified ones. Returns new file entries for lock."""
    old_files = old_lock.get("files", {})
    new_files: dict[str, dict] = {}

    for dest_rel, src_path in sorted(files_to_sync.items()):
        dest = Path(dest_rel)
        source_rel = str(src_path.relative_to(briefcase_dir))
        new_hash = hash_file(src_path)

        if dest.exists():
            current_hash = hash_file(dest)
            if dest_rel in old_files:
                locked_hash = old_files[dest_rel].get("sha256", "")
                if current_hash != locked_hash:
                    print(f"briefcase: SKIPPING {dest_rel} (locally modified)")
                    new_files[dest_rel] = {
                        "sha256": current_hash,
                        "source": source_rel,
                    }
                    continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        new_files[dest_rel] = {"sha256": new_hash, "source": source_rel}
        print(f"briefcase: synced {dest_rel}")

    return new_files


def cleanup_removed(old_lock: dict, new_managed_files: dict[str, dict]) -> None:
    old_files = old_lock.get("files", {})
    for file_path in old_files:
        if file_path not in new_managed_files:
            p = Path(file_path)
            if p.exists():
                p.unlink()
                print(f"briefcase: removed {file_path} (no longer in briefcase)")
            # Clean up empty parent directories
            parent = p.parent
            while parent != Path("."):
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent


def update_gitignore(managed_files: dict[str, dict]) -> None:
    gitignore = Path(".gitignore")
    lines: list[str] = []
    if gitignore.exists():
        lines = gitignore.read_text().splitlines()

    # Build the managed section
    managed_section = [MARKER_BEGIN]
    for file_path in sorted(managed_files):
        managed_section.append(f"/{file_path}")
    managed_section.append(MARKER_END)

    # Find existing markers
    begin_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line == MARKER_BEGIN:
            begin_idx = i
        elif line == MARKER_END:
            end_idx = i

    if begin_idx is not None and end_idx is not None:
        lines[begin_idx : end_idx + 1] = managed_section
    else:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(managed_section)

    gitignore.write_text("\n".join(lines) + "\n")


def run_post_sync_hook() -> None:
    hook = Path(POST_SYNC_HOOK)
    if hook.exists() and os.access(hook, os.X_OK):
        print(f"briefcase: running {POST_SYNC_HOOK}")
        subprocess.run(["bash", str(hook)], check=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync AI agent config from a briefcase repo.")
    parser.add_argument(
        "--briefcase",
        default=None,
        help=(
            "Path to the briefcase repo (relative or absolute). "
            f"Defaults to a sibling directory named '{DEFAULT_BRIEFCASE_DIR_NAME}'."
        ),
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Project folder name inside the briefcase. Defaults to the target repo's directory name.",
    )
    parser.add_argument(
        "--shared",
        default=DEFAULT_SHARED_FOLDER,
        help=f"Shared folder name inside the briefcase (default: '{DEFAULT_SHARED_FOLDER}').",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    project_dir = Path.cwd()
    project_name = args.project or project_dir.name

    env_briefcase = os.environ.get("BRIEFCASE_PATH")
    if env_briefcase:
        briefcase_dir = Path(env_briefcase).resolve()
    elif args.briefcase:
        briefcase_dir = Path(args.briefcase).resolve()
    else:
        briefcase_dir = project_dir.parent / DEFAULT_BRIEFCASE_DIR_NAME

    if not briefcase_dir.is_dir():
        print(
            f"briefcase: WARNING — briefcase repo not found at '{briefcase_dir}', skipping sync.",
            file=sys.stderr,
        )
        return 0

    # Check if briefcase is behind remote
    check_briefcase_staleness(briefcase_dir)

    # Read current lock
    lock_path = Path(LOCK_FILE)
    old_lock = read_lock(lock_path)

    # Get briefcase commit
    source_commit = get_briefcase_commit(briefcase_dir)

    # Collect files with layering
    files_to_sync = collect_files(briefcase_dir, project_name, args.shared)

    if not files_to_sync:
        print(
            f"briefcase: WARNING — no files found in briefcase for project '{project_name}', skipping sync.",
            file=sys.stderr,
        )
        cleanup_removed(old_lock, {})
        update_gitignore({})
        write_lock(lock_path, source_commit, {})
        return 0

    # Sync files
    new_files = sync_files(files_to_sync, old_lock, briefcase_dir)

    # Clean up removed files
    cleanup_removed(old_lock, new_files)

    # Update .gitignore
    update_gitignore(new_files)

    # Write lock file
    write_lock(lock_path, source_commit, new_files)

    # Run post-sync hook
    run_post_sync_hook()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
