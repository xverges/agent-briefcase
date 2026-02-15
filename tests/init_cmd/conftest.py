"""Pytest configuration for init e2e tests.

Routes approved/received files to the approved_files/ subdirectory
and generates SCENARIOS-init.md after each test run.
"""

from __future__ import annotations

from pathlib import Path

from tests.scenario_report import generate_report

SUITE_DIR = Path(__file__).parent
APPROVED_DIR = SUITE_DIR / "approved_files"
SCENARIOS_MD = SUITE_DIR.parents[1] / "SCENARIOS-init.md"


def pytest_sessionfinish(session, exitstatus):
    generate_report(
        title="Briefcase-Init Scenarios",
        approved_dir=APPROVED_DIR,
        output_path=SCENARIOS_MD,
    )
