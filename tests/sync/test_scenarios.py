"""End-to-end scenarios for briefcase-sync."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    shared: str = "_shared",
    subprocess_side_effect: object = None,
) -> tuple[int, str, str]:
    """Run briefcase_sync.main() inside target_dir, capturing stdout/stderr.

    If subprocess_side_effect is given, subprocess.run is mocked with that
    side_effect (useful for controlling git commands in staleness tests).
    """
    project = project_name or target_dir.name
    argv = ["--briefcase", str(briefcase_dir), "--project", project, "--shared", shared]

    stdout, stderr = StringIO(), StringIO()
    original_cwd = os.getcwd()
    try:
        os.chdir(target_dir)
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            if subprocess_side_effect is not None:
                with patch("subprocess.run", side_effect=subprocess_side_effect):
                    exit_code = briefcase_sync.main(argv)
            else:
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
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# shared rules")
        write_file(briefcase / "config" / "_shared" / ".claude" / "commands" / "review.md", "/review command")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Fresh sync copies all files when no prior state exists")
        story.add_frame(
            "briefcase/_shared/CLAUDE.md\nbriefcase/_shared/.claude/commands/review.md",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)

    def test_2_incremental_sync_new_file_added(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        write_file(briefcase / "config" / "_shared" / "new-file.md", "# new content")
        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Incremental sync picks up newly added files")
        story.add_frame("CLAUDE.md (already synced)\nnew-file.md (just added)", "Briefcase contents")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)

    def test_3_incremental_sync_file_removed(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "config" / "_shared" / ".claude" / "commands" / "review.md", "/review")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        (briefcase / "config" / "_shared" / ".claude" / "commands" / "review.md").unlink()
        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Removing a file from the briefcase cleans it up in the target")
        story.add_frame("CLAUDE.md (kept)\n.claude/commands/review.md (removed from briefcase)", "Briefcase change")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)

    def test_4_incremental_sync_file_updated(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# version 1")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        content_before = (target / "CLAUDE.md").read_text()
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# version 2")
        exit_code, stdout, stderr = run_sync(briefcase, target)
        content_after = (target / "CLAUDE.md").read_text()

        story = scenario("Updated briefcase files are synced to the target")
        story.add_frame(f"before: {content_before!r}\nafter:  {content_after!r}", "CLAUDE.md content")
        add_result(story, exit_code, stdout, stderr)
        verify(story)


class TestLayeringAndOverrides_2:
    def test_1_shared_only_sync(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# shared config")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Files sync from _shared/ when no project-specific folder exists")
        story.add_frame("briefcase/_shared/CLAUDE.md\n(no my-project/ folder)", "Briefcase contents")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)

    def test_2_project_overrides_shared(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# shared version")
        write_file(briefcase / "config" / "my-project" / "CLAUDE.md", "# project-specific version")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)
        synced_content = (target / "CLAUDE.md").read_text()

        story = scenario("Project-specific files override shared files at the same path")
        story.add_frame(
            "_shared/CLAUDE.md      → '# shared version'\nmy-project/CLAUDE.md   → '# project-specific version'",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(synced_content, "CLAUDE.md in target (project wins)")
        verify(story)

    def test_3_mixed_shared_and_project_files(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / ".claude" / "commands" / "review.md", "/review from shared")
        write_file(briefcase / "config" / "my-project" / "CLAUDE.md", "# project CLAUDE.md")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Shared and project-specific files are both synced")
        story.add_frame(
            "_shared/.claude/commands/review.md  (from _shared)\nmy-project/CLAUDE.md                (from project)",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)


class TestLocalModificationProtection_3:
    def test_1_locally_modified_file_is_preserved(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# from briefcase")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        (target / "CLAUDE.md").write_text("# my local edits")
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# updated in briefcase")
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
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# v1")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# v2")
        exit_code, stdout, stderr = run_sync(briefcase, target)
        final_content = (target / "CLAUDE.md").read_text()

        story = scenario("Unmodified synced files are updated when the briefcase changes")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(final_content, "CLAUDE.md in target (updated to v2)")
        verify(story)


class TestGitignoreManagement_4:
    def test_1_synced_files_added_to_gitignore(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "config" / "_shared" / ".claude" / "commands" / "review.md", "/review")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)

        story = scenario("All synced files appear in a managed .gitignore section")
        story.add_frame(read_gitignore(target), ".gitignore")
        verify(story)

    def test_2_removed_files_cleaned_from_gitignore(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "config" / "_shared" / "extra.md", "# extra")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        gitignore_before = read_gitignore(target)
        (briefcase / "config" / "_shared" / "extra.md").unlink()
        run_sync(briefcase, target)
        gitignore_after = read_gitignore(target)

        story = scenario("Removed files are cleaned from .gitignore")
        story.add_frame(gitignore_before, ".gitignore before")
        story.add_frame(gitignore_after, ".gitignore after (extra.md removed)")
        verify(story)

    def test_3_existing_gitignore_content_preserved(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

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
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

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
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

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
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# from custom path")

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
        write_file(briefcase / "config" / "custom-name" / "CLAUDE.md", "# for custom-name project")

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

    def test_3_env_var_overrides_cli_briefcase_path(self, tmp_path: Path) -> None:
        """BRIEFCASE_PATH env var takes precedence over --briefcase."""
        cli_briefcase = tmp_path / "cli-briefcase"
        write_file(cli_briefcase / "config" / "_shared" / "CLAUDE.md", "# from CLI path")

        env_briefcase = tmp_path / "env-briefcase"
        write_file(env_briefcase / "config" / "_shared" / "CLAUDE.md", "# from BRIEFCASE_PATH")

        target = tmp_path / "my-project"
        target.mkdir()

        with patch.dict(os.environ, {"BRIEFCASE_PATH": str(env_briefcase)}):
            exit_code, stdout, stderr = run_sync(cli_briefcase, target)
        synced_content = (target / "CLAUDE.md").read_text()

        story = scenario("BRIEFCASE_PATH env var overrides --briefcase CLI argument")
        story.add_frame(
            "--briefcase points to cli-briefcase/ with '# from CLI path'\n"
            "BRIEFCASE_PATH points to env-briefcase/ with '# from BRIEFCASE_PATH'",
            "Setup",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(synced_content, "CLAUDE.md content (env var wins)")
        verify(story)

    def test_4_custom_shared_name(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "common" / "CLAUDE.md", "# from common/")
        write_file(briefcase / "config" / "_shared" / "IGNORED.md", "# should not sync")

        target = tmp_path / "my-project"
        target.mkdir()

        exit_code, stdout, stderr = run_sync(briefcase, target, shared="common")

        story = scenario("Custom --shared folder name uses the specified folder instead of '_shared/'")
        story.add_frame(
            "briefcase/common/CLAUDE.md    (should sync)\nbriefcase/_shared/IGNORED.md  (should NOT sync)",
            "Briefcase contents",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)


class TestLockFileIntegrity_8:
    def test_1_lock_file_records_state(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)

        story = scenario("Lock file records source commit and file hashes after sync")
        story.add_frame(read_lock_data(target), ".briefcase.lock")
        verify(story)

    def test_2_idempotent_sync_no_changes(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        run_sync(briefcase, target)
        exit_code, stdout, stderr = run_sync(briefcase, target)

        story = scenario("Re-running sync with no changes is idempotent")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory (unchanged)")
        verify(story)


# ---------------------------------------------------------------------------
# Staleness detection helpers
# ---------------------------------------------------------------------------


def _git_mock(
    *,
    local_sha: str = "aaa1111",
    remote_sha: str | None = None,
    behind_count: str = "0",
    fetch_fails: bool = False,
    not_a_repo: bool = False,
    no_remote_ref: bool = False,
):
    """Build a subprocess.run side_effect that simulates git staleness scenarios."""

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if not_a_repo and ("rev-parse" in cmd_str or "fetch" in cmd_str):
            raise subprocess.CalledProcessError(128, cmd)
        if "fetch" in cmd_str:
            if fetch_fails:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)
        if "rev-parse HEAD" in cmd_str:
            result = MagicMock()
            result.stdout = local_sha + "\n"
            return result
        if "rev-parse origin/" in cmd_str:
            if no_remote_ref:
                raise subprocess.CalledProcessError(128, cmd)
            result = MagicMock()
            result.stdout = (remote_sha or local_sha) + "\n"
            return result
        if "rev-list --count" in cmd_str:
            result = MagicMock()
            result.stdout = behind_count + "\n"
            return result
        return MagicMock()

    return fake_run


class TestStalenessDetection_9:
    def test_1_warns_when_briefcase_is_behind_remote(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        mock = _git_mock(local_sha="aaa1111", remote_sha="bbb2222", behind_count="3")
        exit_code, stdout, stderr = run_sync(briefcase, target, subprocess_side_effect=mock)

        story = scenario("Stale briefcase emits a warning but sync proceeds normally")
        story.add_frame("local HEAD: aaa1111\nremote HEAD: bbb2222 (3 commits ahead)", "Briefcase git state")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(target_tree(target), "Target directory after sync")
        verify(story)

    def test_2_no_warning_when_up_to_date(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        mock = _git_mock(local_sha="aaa1111", remote_sha="aaa1111")
        exit_code, stdout, stderr = run_sync(briefcase, target, subprocess_side_effect=mock)

        story = scenario("Up-to-date briefcase produces no staleness warning")
        story.add_frame("local HEAD: aaa1111\nremote HEAD: aaa1111 (same)", "Briefcase git state")
        add_result(story, exit_code, stdout, stderr)
        verify(story)

    def test_3_no_warning_when_fetch_fails(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        mock = _git_mock(fetch_fails=True)
        exit_code, stdout, stderr = run_sync(briefcase, target, subprocess_side_effect=mock)

        story = scenario("Offline / fetch failure skips staleness check silently")
        story.add_frame("git fetch → fails (e.g. no network)", "Briefcase git state")
        add_result(story, exit_code, stdout, stderr)
        verify(story)

    def test_4_no_warning_when_not_a_git_repo(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        mock = _git_mock(not_a_repo=True)
        exit_code, stdout, stderr = run_sync(briefcase, target, subprocess_side_effect=mock)

        story = scenario("Non-git briefcase directory skips staleness check")
        story.add_frame("git rev-parse → fails (not a git repo)", "Briefcase git state")
        add_result(story, exit_code, stdout, stderr)
        verify(story)

    def test_5_no_warning_when_remote_ref_not_found(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config" / "_shared" / "CLAUDE.md", "# rules")

        target = tmp_path / "my-project"
        target.mkdir()

        mock = _git_mock(no_remote_ref=True)
        exit_code, stdout, stderr = run_sync(briefcase, target, subprocess_side_effect=mock)

        story = scenario("Missing remote tracking branch skips staleness check")
        story.add_frame("git fetch → ok\ngit rev-parse origin/main → fails (no remote ref)", "Briefcase git state")
        add_result(story, exit_code, stdout, stderr)
        verify(story)


class TestSymlinkSupport_10:
    def test_1_symlinked_project_files_are_synced_as_copies(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        # No _shared/AGENTS.md — projectA owns the canonical file
        write_file(briefcase / "config" / "projectA" / "AGENTS.md", "# projectA agent rules")

        # projectB symlinks to projectA's file instead of duplicating it
        (briefcase / "config" / "projectB").mkdir(parents=True)
        (briefcase / "config" / "projectB" / "AGENTS.md").symlink_to(briefcase / "config" / "projectA" / "AGENTS.md")

        target_a = tmp_path / "projectA"
        target_a.mkdir()
        target_b = tmp_path / "projectB"
        target_b.mkdir()

        exit_a, stdout_a, _stderr_a = run_sync(briefcase, target_a)
        exit_b, stdout_b, _stderr_b = run_sync(briefcase, target_b)

        # Both targets should have a regular file (not a symlink)
        agents_a = target_a / "AGENTS.md"
        agents_b = target_b / "AGENTS.md"

        story = scenario("Symlinked files in briefcase project folders are synced as regular copies")
        story.add_frame(
            "projectA/AGENTS.md         → '# projectA agent rules' (real file)\n"
            "projectB/AGENTS.md         → symlink to projectA/AGENTS.md",
            "Briefcase contents",
        )
        story.add_frame(format_output(stdout_a), "projectA stdout")
        story.add_frame(exit_a, "projectA exit code")
        story.add_frame(format_output(stdout_b), "projectB stdout")
        story.add_frame(exit_b, "projectB exit code")
        story.add_frame(agents_a.read_text(), "projectA AGENTS.md content")
        story.add_frame(agents_b.read_text(), "projectB AGENTS.md content")
        story.add_frame(str(agents_a.is_symlink()), "projectA AGENTS.md is symlink?")
        story.add_frame(str(agents_b.is_symlink()), "projectB AGENTS.md is symlink?")
        verify(story)
