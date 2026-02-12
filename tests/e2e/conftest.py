"""Pytest configuration for e2e tests.

- Routes approved/received files to the approved_files/ subdirectory.
- Generates SCENARIOS.md from approved files, using test class names as sections.

Conventions:
- Class names end with _N for section ordering: TestCoreSync_1, TestLayering_2, ...
- Test methods start with test_N_ for ordering within a section: test_1_foo, test_2_bar, ...
- Section titles and scenario titles are derived automatically by stripping these prefixes.
"""

from __future__ import annotations

import re
from pathlib import Path

E2E_DIR = Path(__file__).parent
APPROVED_DIR = E2E_DIR / "approved_files"
SCENARIOS_MD = E2E_DIR.parents[1] / "SCENARIOS.md"

AUTOGEN_HEADER = (
    "> **Auto-generated** from approved test output — do not edit by hand.\n> Re-run `pytest` to regenerate.\n"
)


# ---------------------------------------------------------------------------
# SCENARIOS.md generation
# ---------------------------------------------------------------------------


def _test_sort_key(test_name: str) -> int:
    """Extract the test_N_ prefix as sort key."""
    match = re.match(r"test_(\d+)_", test_name)
    return int(match.group(1)) if match else 999


def _parse_approved_filename(filename: str) -> tuple[str | None, str]:
    """Parse 'ClassName.test_name.approved.txt' → (class_name, test_name)."""
    stem = filename.replace(".approved.txt", "")
    parts = stem.split(".", 1)
    if len(parts) == 2 and not parts[0].startswith("test_"):
        return parts[0], parts[1]
    return None, stem


def _class_to_section(class_name: str | None) -> str:
    """Derive section title from class name.

    'TestCoreSync_1' → 'Core Sync'
    'TestLayeringAndOverrides_2' → 'Layering & Overrides'
    """
    if not class_name:
        return "Other"
    # Strip 'Test' prefix and '_N' suffix
    stripped = re.sub(r"^Test|_\d+$", "", class_name)
    # CamelCase → spaced
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", stripped)
    return spaced.replace(" And ", " & ")


def _class_sort_key(class_name: str | None) -> int:
    """Extract the _N suffix as sort key. Classes without a suffix sort last."""
    if not class_name:
        return 999
    match = re.search(r"_(\d+)$", class_name)
    return int(match.group(1)) if match else 999


def _test_title(test_name: str) -> str:
    """'test_2_incremental_sync_new_file_added' → 'Incremental sync new file added'."""
    stripped = re.sub(r"^test_\d+_", "", test_name)
    return stripped.replace("_", " ").capitalize()


def pytest_sessionfinish(session, exitstatus):
    # Build entries from approved files
    entries: list[tuple[str | None, str, Path]] = []
    for path in APPROVED_DIR.glob("*.approved.txt"):
        class_name, test_name = _parse_approved_filename(path.name)
        entries.append((class_name, test_name, path))

    if not entries:
        return

    # Group by section, sorting by the numbering conventions
    sections: dict[str, list[tuple[str, Path]]] = {}
    section_sort_keys: dict[str, int] = {}
    for class_name, test_name, path in entries:
        section = _class_to_section(class_name)
        sections.setdefault(section, []).append((test_name, path))
        section_sort_keys.setdefault(section, _class_sort_key(class_name))

    # Sort tests within each section by their test_N_ prefix
    for section in sections:
        sections[section].sort(key=lambda t: _test_sort_key(t[0]))

    # Sort sections by their class _N suffix
    sorted_sections = sorted(sections.keys(), key=lambda s: section_sort_keys.get(s, 999))

    lines = ["# Briefcase-Sync E2E Scenarios\n", AUTOGEN_HEADER]
    scenario_num = 1

    for section_title in sorted_sections:
        tests = sections[section_title]
        lines.append(f"\n## {section_title}\n")
        for test_name, path in tests:
            content = path.read_text().strip()
            title = _test_title(test_name)
            lines.append(f"### {scenario_num}. {title}\n")
            lines.append(f"```\n{content}\n```\n")
            scenario_num += 1

    SCENARIOS_MD.write_text("\n".join(lines) + "\n")
