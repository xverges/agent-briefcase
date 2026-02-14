"""Shared logic for generating SCENARIOS-*.md files from approved test output.

Each test suite's conftest.py calls ``generate_report()`` with the appropriate
paths.

Conventions:
- Class names end with _N for section ordering: TestCoreSync_1, TestLayering_2, ...
- Test methods start with test_N_ for ordering within a section: test_1_foo, test_2_bar, ...
- Section titles and scenario titles are derived automatically by stripping these prefixes.
"""

from __future__ import annotations

import re
from pathlib import Path

AUTOGEN_HEADER = (
    "> **Auto-generated** from approved test output — do not edit by hand.\n> Re-run `pytest` to regenerate.\n"
)


def _test_sort_key(test_name: str) -> int:
    match = re.match(r"test_(\d+)_", test_name)
    return int(match.group(1)) if match else 999


def _parse_approved_filename(filename: str) -> tuple[str | None, str]:
    stem = filename.replace(".approved.txt", "")
    parts = stem.split(".", 1)
    if len(parts) == 2 and not parts[0].startswith("test_"):
        return parts[0], parts[1]
    return None, stem


def _class_to_section(class_name: str | None) -> str:
    if not class_name:
        return "Other"
    stripped = re.sub(r"^Test|_\d+$", "", class_name)
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", stripped)
    return spaced.replace(" And ", " & ")


def _class_sort_key(class_name: str | None) -> int:
    if not class_name:
        return 999
    match = re.search(r"_(\d+)$", class_name)
    return int(match.group(1)) if match else 999


def _test_title(test_name: str) -> str:
    stripped = re.sub(r"^test_\d+_", "", test_name)
    return stripped.replace("_", " ").capitalize()


def generate_report(*, title: str, approved_dir: Path, output_path: Path) -> None:
    """Generate a SCENARIOS markdown file from approved test output files."""
    entries: list[tuple[str | None, str, Path]] = []
    for path in approved_dir.glob("*.approved.txt"):
        class_name, test_name = _parse_approved_filename(path.name)
        entries.append((class_name, test_name, path))

    if not entries:
        return

    sections: dict[str, list[tuple[str, Path]]] = {}
    section_sort_keys: dict[str, int] = {}
    for class_name, test_name, path in entries:
        section = _class_to_section(class_name)
        sections.setdefault(section, []).append((test_name, path))
        section_sort_keys.setdefault(section, _class_sort_key(class_name))

    for section in sections:
        sections[section].sort(key=lambda t: _test_sort_key(t[0]))

    sorted_sections = sorted(sections.keys(), key=lambda s: section_sort_keys.get(s, 999))

    lines = [f"# {title}\n", AUTOGEN_HEADER]
    scenario_num = 1

    for section_title in sorted_sections:
        tests = sections[section_title]
        lines.append(f"\n## {section_title}\n")
        for test_name, path in tests:
            content = path.read_text().strip()
            title_text = _test_title(test_name)
            lines.append(f"### {scenario_num}. {title_text}\n")
            lines.append(f"```\n{content}\n```\n")
            scenario_num += 1

    output_path.write_text("\n".join(lines) + "\n")
