"""End-to-end scenarios for briefcase-sync."""

from __future__ import annotations

import json
import os
import stat
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from approvaltests import verify
from approvaltests.storyboard import Storyboard

import briefcase_sync

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_sync(
    briefcase_dir: Path,
    target_dir: Path,
    project_name: str | None = None,
    shared: str = "shared",
) -> tuple[int, str, str]:
    """Run briefcase_sync.main() inside target_dir, capturing stdout/stderr."""
    project = project_name or target_dir.name
    argv = ["--briefcase", str(briefcase_dir), "--project", project, "--shared", shared]

    stdout, stderr = StringIO(), StringIO()
    original_cwd = os.getcwd()
    try:
        os.chdir(target_dir)
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = briefcase_sync.main(argv)
    finally:
        os.chdir(original_cwd)

    # Scrub absolute tmp paths so approved files are stable across runs
    tmp_root = str(target_dir.parent)
    return (
        exit_code,
        stdout.getvalue().replace(tmp_root, "<tmp>"),
        stderr.getvalue().replace(tmp_root, "<tmp>"),
    )


def write_file(path: Path, content: str = "") -> None:
    """Create a file with content, making parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def target_tree(target_dir: Path) -> str:
    """Tree of the target dir files."""
    lines = []
    for entry in sorted(target_dir.rglob("*")):
        if entry.is_file():
            rel = entry.relative_to(target_dir)
            lines.append(str(rel))
    return "\n".join(lines) if lines else "(empty)"


def format_output(text: str) -> str:
    """Format captured output for the storyboard."""
    if not text.strip():
        return "(empty)"
    return textwrap.indent(text.rstrip(), "  ")


def read_lock_data(target_dir: Path) -> str:
    """Read and format lock file contents, scrubbing the commit hash."""
    lock_path = target_dir / ".briefcase.lock"
    if not lock_path.exists():
        return "(no lock file)"
    data = json.loads(lock_path.read_text())
    data["source_commit"] = "<commit>"
    return json.dumps(data, indent=2, sort_keys=True)


def read_gitignore(target_dir: Path) -> str:
    """Read .gitignore contents."""
    gi = target_dir / ".gitignore"
    if not gi.exists():
        return "(no .gitignore)"
    return gi.read_text().rstrip()


def scenario(description: str) -> Storyboard:
    """Start a new storyboard with a scenario description."""
    story = Storyboard()
    story.add_description(f"Scenario: {description}")
    return story


def add_result(story: Storyboard, exit_code: int, stdout: str, stderr: str) -> None:
    """Add the standard result frames to a storyboard."""
    story.add_frame(format_output(stdout), "stdout")
    story.add_frame(format_output(stderr), "stderr")
    story.add_frame(exit_code, "exit code")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


class TestCoreSync_1:
    def test_1_fresh_sync_copies_all_files(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# shared rules")
        write_file(briefcase / "shared" / ".claude" / "commands" / "review.md", "/review command")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Fresh sync copies all files when no prior state exists")
        story.add_frame(
            "briefcase/shared/CLAUDE.md\nbriefcase/shared/.claude/commands/review.md",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)

    def test_2_incremental_sync_new_file_added(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        write_file(briefcase / "shared" / "new-file.md", "# new content")
        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Incremental sync picks up newly added files")
        story.add_frame("CLAUDE.md (already synced)\nnew-file.md (just added)", "Briefcase contents")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)

    def test_3_incremental_sync_file_removed(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "shared" / ".claude" / "commands" / "review.md", "/review")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        (briefcase / "shared" / ".claude" / "commands" / "review.md").unlink()
        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Removing a file from the briefcase cleans it up in the target")
        story.add_frame("CLAUDE.md (kept)\n.claude/commands/review.md (removed from briefcase)", "Briefcase change")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)

    def test_4_incremental_sync_file_updated(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# version 1")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        content_before = (target / "CLAUDE.md").read_text()
        write_file(briefcase / "shared" / "CLAUDE.md", "# version 2")
        exit_code, stdout, stderr = run_sync(briefcase, target)
        content_after = (target / "CLAUDE.md").read_text()

        story = scenario("Updated briefcase files are synced to the target")
        story.add_frame(f"before: {content_before!r}\nafter:  {content_after!r}", "CLAUDE.md content")
        add_result(story, exit_code, stdout, stderr)
        verify(story)


class TestLayeringAndOverrides_2:
    def test_1_shared_only_sync(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# shared config")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Files sync from shared/ when no project-specific folder exists")
        story.add_frame("briefcase/shared/CLAUDE.md\n(no my-project/ folder)", "Briefcase contents")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)

    def test_2_project_overrides_shared(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# shared version")
        write_file(briefcase / "my-project" / "CLAUDE.md", "# project-specific version")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)
        synced_content = (target / "CLAUDE.md").read_text()

        story = scenario("Project-specific files override shared files at the same path")
        story.add_frame(
            "shared/CLAUDE.md       → '# shared version'\nmy-project/CLAUDE.md   → '# project-specific version'",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(synced_content, "CLAUDE.md in target (project wins)")
        verify(story)

    def test_3_mixed_shared_and_project_files(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / ".claude" / "commands" / "review.md", "/review from shared")
        write_file(briefcase / "my-project" / "CLAUDE.md", "# project CLAUDE.md")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Shared and project-specific files are both synced")
        story.add_frame(
            "shared/.claude/commands/review.md  (from shared)\nmy-project/CLAUDE.md                (from project)",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)


class TestLocalModificationProtection_3:
    def test_1_locally_modified_file_is_preserved(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# from briefcase")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        (target / "CLAUDE.md").write_text("# my local edits")
        write_file(briefcase / "shared" / "CLAUDE.md", "# updated in briefcase")
        exit_code, stdout, stderr = run_sync(briefcase, target)
        final_content = (target / "CLAUDE.md").read_text()

        story = scenario("Locally modified files are preserved with a warning")
        story.add_frame(
            "briefcase CLAUDE.md: '# updated in briefcase'\nlocal CLAUDE.md:     '# my local edits'",
            "Conflict",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(final_content, "CLAUDE.md in target (local edit preserved)")
        verify(story)

    def test_2_unmodified_file_is_updated(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# v1")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        write_file(briefcase / "shared" / "CLAUDE.md", "# v2")
        exit_code, stdout, stderr = run_sync(briefcase, target)
        final_content = (target / "CLAUDE.md").read_text()

        story = scenario("Unmodified synced files are updated when the briefcase changes")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(final_content, "CLAUDE.md in target (updated to v2)")
        verify(story)


class TestGitignoreManagement_4:
    def test_1_synced_files_added_to_gitignore(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "shared" / ".claude" / "commands" / "review.md", "/review")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)

        story = scenario("All synced files appear in a managed .gitignore section")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)

    def test_2_removed_files_cleaned_from_gitignore(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "shared" / "extra.md", "# extra")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        gitignore_before = read_gitignore(target)
        (briefcase / "shared" / "extra.md").unlink()
        run_sync(briefcase, target)
        gitignore_after = read_gitignore(target)

        story = scenario("Removed files are cleaned from .gitignore")
        story.add_frame(gitignore_before, ".gitignore before")
        story.add_frame(gitignore_after, ".gitignore after (extra.md removed)")
        verify(story)

    def test_3_existing_gitignore_content_preserved(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()
        (target / ".gitignore").write_text("node_modules/\n.env\n")

        run_sync(briefcase, target)

        story = scenario("Existing .gitignore entries are preserved alongside managed section")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)


class TestPostSyncHook_5:
    def test_1_post_sync_hook_runs(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        hook = target / ".briefcase-post-sync.sh"
        hook.write_text("#!/bin/bash\necho 'hook-was-here' > .post-sync-marker\n")
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

        exit_code, stdout, stderr = run_sync(briefcase, target)
        marker_exists = (target / ".post-sync-marker").exists()
        marker_content = (target / ".post-sync-marker").read_text().strip() if marker_exists else "(not created)"

        story = scenario("Post-sync hook runs after files are synced")
        story.add_frame("#!/bin/bash\necho 'hook-was-here' > .post-sync-marker", ".briefcase-post-sync.sh")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(marker_content, ".post-sync-marker content")
        verify(story)

    def test_2_no_post_sync_hook_is_noop(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Sync completes normally when no post-sync hook exists")
        story.add_frame("(no .briefcase-post-sync.sh in target)", "Setup")
        add_result(story, exit_code, stdout, stderr)
        verify(story)


class TestGracefulDegradation_6:
    def test_1_missing_briefcase_repo(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "nonexistent-briefcase"
        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Missing briefcase repo warns on stderr and exits successfully (CI-friendly)")
        add_result(story, exit_code, stdout, stderr)
        verify(story)

    def test_2_empty_briefcase_emits_warning(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        briefcase.mkdir()

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Empty briefcase emits a warning")
        story.add_frame("briefcase/  (exists, empty)\nmy-project/  (exists)", "Setup")
        add_result(story, exit_code, stdout, stderr)
        verify(story)


class TestCLIConfiguration_7:
    def test_1_custom_briefcase_path(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "somewhere" / "else" / "my-briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# from custom path")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)
        synced_content = (target / "CLAUDE.md").read_text()

        story = scenario("Custom --briefcase path resolves files from a non-sibling directory")
        story.add_frame(str(briefcase.relative_to(tmp_path)), "Briefcase relative path")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(synced_content, "CLAUDE.md content")
        verify(story)

    def test_2_custom_project_name(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "custom-name" / "CLAUDE.md", "# for custom-name project")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target, project_name="custom-name")
        synced_content = (target / "CLAUDE.md").read_text()

        story = scenario("Custom --project name picks up files from the named folder")
        story.add_frame(
            "briefcase/custom-name/CLAUDE.md exists\ntarget dir is 'my-project' but --project=custom-name",
            "Setup",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(synced_content, "CLAUDE.md content")
        verify(story)

    def test_3_custom_shared_name(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "common" / "CLAUDE.md", "# from common/")
        write_file(briefcase / "shared" / "IGNORED.md", "# should not sync")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target, shared="common")

        story = scenario("Custom --shared folder name uses the specified folder instead of 'shared/'")
        story.add_frame(
            "briefcase/common/CLAUDE.md   (should sync)\nbriefcase/shared/IGNORED.md  (should NOT sync)",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)


class TestLockFileIntegrity_8:
    def test_1_lock_file_records_state(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)

        story = scenario("Lock file records source commit and file hashes after sync")
        story.add_frame(read_lock_data(target), ".briefcase.lock")
        verify(story)

    def test_2_idempotent_sync_no_changes(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Re-running sync with no changes is idempotent")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory (unchanged)")
        verify(story)
