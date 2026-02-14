"""End-to-end scenarios for briefcase-build."""

from __future__ import annotations

import os
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from approvaltests import verify
from approvaltests.storyboard import Storyboard

import briefcase_build

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_build(briefcase_dir: Path) -> tuple[int, str, str]:
    """Run briefcase_build.build() inside briefcase_dir, capturing stdout/stderr."""
    stdout, stderr = StringIO(), StringIO()
    original_cwd = os.getcwd()
    try:
        os.chdir(briefcase_dir)
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = briefcase_build.main()
    finally:
        os.chdir(original_cwd)

    return exit_code, stdout.getvalue(), stderr.getvalue()


def write_file(path: Path, content: str = "") -> None:
    """Create a file with content, making parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def config_tree(briefcase_dir: Path) -> str:
    """Tree of config/ output files."""
    config_dir = briefcase_dir / "config"
    if not config_dir.is_dir():
        return "(no config/ directory)"
    lines = []
    for entry in sorted(config_dir.rglob("*")):
        if entry.is_file():
            rel = entry.relative_to(config_dir)
            lines.append(str(rel))
    return "\n".join(lines) if lines else "(empty)"


def read_file(path: Path) -> str:
    """Read a file's content."""
    if not path.exists():
        return "(file does not exist)"
    return path.read_text()


def format_output(text: str) -> str:
    """Format captured output for the storyboard."""
    if not text.strip():
        return "(empty)"
    return textwrap.indent(text.rstrip(), "  ")


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


class TestBasicBuild_1:
    def test_1_basic_build_copies_files(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_shared" / "CLAUDE.md", "# shared rules")
        write_file(briefcase / "config-src" / "projectA" / "CLAUDE.md", "# projectA rules")

        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("Basic build with no includes copies files verbatim to config/")
        story.add_frame(
            "config-src/_shared/CLAUDE.md\nconfig-src/projectA/CLAUDE.md",
            "Source files",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(config_tree(briefcase), "config/ after build")
        story.add_frame(
            read_file(briefcase / "config" / "_shared" / "CLAUDE.md"),
            "config/_shared/CLAUDE.md",
        )
        story.add_frame(
            read_file(briefcase / "config" / "projectA" / "CLAUDE.md"),
            "config/projectA/CLAUDE.md",
        )
        verify(story)


class TestIncludeExpansion_2:
    def test_1_include_replaces_directive_with_fragment(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_includes" / "debug.md", "## Debug\nUse verbose logging.")
        write_file(
            briefcase / "config-src" / "_shared" / "CLAUDE.md",
            "# Rules\n\n{{include debug.md}}\n\n## Other\nDone.",
        )

        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("Include directive is replaced by the fragment file contents")
        story.add_frame(
            read_file(briefcase / "config-src" / "_shared" / "CLAUDE.md"),
            "config-src/_shared/CLAUDE.md (source)",
        )
        story.add_frame(
            read_file(briefcase / "config-src" / "_includes" / "debug.md"),
            "config-src/_includes/debug.md (fragment)",
        )
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(
            read_file(briefcase / "config" / "_shared" / "CLAUDE.md"),
            "config/_shared/CLAUDE.md (built)",
        )
        verify(story)


class TestNestedIncludes_3:
    def test_1_nested_includes_are_resolved(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_includes" / "inner.md", "inner content")
        write_file(briefcase / "config-src" / "_includes" / "outer.md", "before\n{{include inner.md}}\nafter")
        write_file(
            briefcase / "config-src" / "_shared" / "CLAUDE.md",
            "# Top\n{{include outer.md}}\n# Bottom",
        )

        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("Nested includes are fully resolved (fragment includes another fragment)")
        story.add_frame("outer.md includes inner.md\nCLAUDE.md includes outer.md", "Include chain")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(
            read_file(briefcase / "config" / "_shared" / "CLAUDE.md"),
            "config/_shared/CLAUDE.md (built)",
        )
        verify(story)


class TestCircularIncludeDetection_4:
    def test_1_circular_includes_produce_error(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_includes" / "a.md", "{{include b.md}}")
        write_file(briefcase / "config-src" / "_includes" / "b.md", "{{include a.md}}")
        write_file(
            briefcase / "config-src" / "_shared" / "CLAUDE.md",
            "{{include a.md}}",
        )

        try:
            run_build(briefcase)
            error = "(no error raised)"
        except ValueError as e:
            error = str(e)

        story = scenario("Circular includes are detected and reported as an error")
        story.add_frame("CLAUDE.md → a.md → b.md → a.md (cycle!)", "Include chain")
        story.add_frame(error, "Error")
        verify(story)


class TestMissingInclude_5:
    def test_1_missing_include_produces_error(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(
            briefcase / "config-src" / "_shared" / "CLAUDE.md",
            "{{include nonexistent.md}}",
        )

        try:
            run_build(briefcase)
            error = "(no error raised)"
        except FileNotFoundError as e:
            error = str(e)

        story = scenario("Missing include file is reported as an error")
        story.add_frame("{{include nonexistent.md}}", "Directive in source")
        story.add_frame(error, "Error")
        verify(story)


class TestIncludesDirNotCopied_6:
    def test_1_includes_dir_not_in_output(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_includes" / "debug.md", "debug stuff")
        write_file(briefcase / "config-src" / "_includes" / "testing.md", "testing stuff")
        write_file(briefcase / "config-src" / "_shared" / "CLAUDE.md", "# rules\n{{include debug.md}}")

        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("Fragment files from _includes/ do not appear in config/ output")
        story.add_frame("_includes/debug.md\n_includes/testing.md\n_shared/CLAUDE.md", "config-src/ contents")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(config_tree(briefcase), "config/ after build (no _includes/)")
        verify(story)


class TestStaleFileCleanup_7:
    def test_1_removed_source_is_removed_from_config(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_shared" / "CLAUDE.md", "# rules")
        write_file(briefcase / "config-src" / "_shared" / "extra.md", "# extra")

        run_build(briefcase)
        tree_before = config_tree(briefcase)

        # Remove extra.md from source
        (briefcase / "config-src" / "_shared" / "extra.md").unlink()
        exit_code, stdout, stderr = run_build(briefcase)
        tree_after = config_tree(briefcase)

        story = scenario("File removed from config-src/ is cleaned up from config/")
        story.add_frame(tree_before, "config/ before (both files)")
        story.add_frame("config-src/_shared/extra.md deleted", "Change")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(tree_after, "config/ after (extra.md removed)")
        verify(story)


class TestNoOpWhenUpToDate_8:
    def test_1_no_changes_exits_zero(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_shared" / "CLAUDE.md", "# rules")

        run_build(briefcase)
        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("Re-running build with no changes exits 0 (up to date)")
        add_result(story, exit_code, stdout, stderr)
        verify(story)


class TestFilesChangedExitsOne_9:
    def test_1_changes_exit_one(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        write_file(briefcase / "config-src" / "_shared" / "CLAUDE.md", "# rules")

        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("Build that writes files exits 1 (files changed)")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(config_tree(briefcase), "config/ after build")
        verify(story)


class TestNoConfigSrcIsNoop_10:
    def test_1_no_config_src_exits_zero(self, tmp_path: Path) -> None:
        briefcase = tmp_path / "briefcase"
        briefcase.mkdir()

        exit_code, stdout, stderr = run_build(briefcase)

        story = scenario("No config-src/ directory is a no-op (exits 0 with a message)")
        story.add_frame("(no config-src/ directory)", "Setup")
        add_result(story, exit_code, stdout, stderr)
        verify(story)
