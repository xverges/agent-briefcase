"""End-to-end scenarios for briefcase-init."""

from __future__ import annotations

import os
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from approvaltests import verify
from approvaltests.storyboard import Storyboard

import briefcase_init

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_init(target_dir: Path) -> tuple[int, str, str]:
    """Run briefcase_init.main() inside target_dir, capturing stdout/stderr."""
    stdout, stderr = StringIO(), StringIO()
    original_cwd = os.getcwd()
    try:
        os.chdir(target_dir)
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = briefcase_init.main()
    finally:
        os.chdir(original_cwd)

    return exit_code, stdout.getvalue(), stderr.getvalue()


def dir_tree(root: Path) -> str:
    """Tree of all files under root, relative paths."""
    lines = []
    for entry in sorted(root.rglob("*")):
        if entry.is_file():
            rel = entry.relative_to(root)
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


class TestScaffoldEmptyDir_1:
    def test_1_init_creates_full_structure(self, tmp_path: Path) -> None:
        target = tmp_path / "briefcase"
        target.mkdir()

        exit_code, stdout, stderr = run_init(target)

        story = scenario("Init in an empty directory creates the full briefcase structure")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(dir_tree(target), "directory tree after init")
        story.add_frame(
            read_file(target / "BRIEFCASE.md") != "(file does not exist)",
            "BRIEFCASE.md exists",
        )
        story.add_frame(
            read_file(target / "config-src" / "_includes" / "README.md") != "(file does not exist)",
            "config-src/_includes/README.md exists",
        )
        story.add_frame(
            (target / "config-src" / "_shared").is_dir(),
            "config-src/_shared/ directory exists",
        )
        story.add_frame(
            read_file(target / "dotfiles" / "README.md") != "(file does not exist)",
            "dotfiles/README.md exists",
        )
        verify(story)


class TestIdempotent_2:
    def test_1_rerun_does_not_overwrite(self, tmp_path: Path) -> None:
        target = tmp_path / "briefcase"
        target.mkdir()

        run_init(target)

        # Modify a generated file
        briefcase_md = target / "BRIEFCASE.md"
        briefcase_md.write_text("custom content")

        exit_code, stdout, stderr = run_init(target)

        story = scenario("Re-running init skips existing files (does not overwrite)")
        story.add_frame("BRIEFCASE.md modified to 'custom content' after first init", "Setup")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(read_file(briefcase_md), "BRIEFCASE.md after second init")
        verify(story)


class TestPartialExisting_3:
    def test_1_creates_missing_skips_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "briefcase"
        target.mkdir()

        # Pre-create some structure
        (target / "config-src" / "_includes").mkdir(parents=True)
        (target / "config-src" / "_includes" / "README.md").write_text("existing includes readme")

        exit_code, stdout, stderr = run_init(target)

        story = scenario("Init with partially existing structure creates missing parts, skips existing")
        story.add_frame("config-src/_includes/README.md already exists with custom content", "Setup")
        add_result(story, exit_code, stdout, stderr)
        story.add_frame(dir_tree(target), "directory tree after init")
        story.add_frame(
            read_file(target / "config-src" / "_includes" / "README.md"),
            "config-src/_includes/README.md (preserved)",
        )
        verify(story)


class TestGeneratedContent_4:
    def test_1_briefcase_md_content(self, tmp_path: Path) -> None:
        target = tmp_path / "briefcase"
        target.mkdir()

        run_init(target)

        story = scenario("BRIEFCASE.md contains operational guide for the team")
        story.add_frame(read_file(target / "BRIEFCASE.md"), "BRIEFCASE.md")
        verify(story)

    def test_2_includes_readme_content(self, tmp_path: Path) -> None:
        target = tmp_path / "briefcase"
        target.mkdir()

        run_init(target)

        story = scenario("config-src/_includes/README.md explains the _includes directory")
        story.add_frame(
            read_file(target / "config-src" / "_includes" / "README.md"),
            "config-src/_includes/README.md",
        )
        verify(story)

    def test_3_dotfiles_readme_content(self, tmp_path: Path) -> None:
        target = tmp_path / "briefcase"
        target.mkdir()

        run_init(target)

        story = scenario("dotfiles/README.md explains the dotfiles directory")
        story.add_frame(
            read_file(target / "dotfiles" / "README.md"),
            "dotfiles/README.md",
        )
        verify(story)
