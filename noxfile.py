"""Nox sessions for CI and local development."""

from __future__ import annotations

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True

PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.install(".[test]")
    session.run("pytest", *session.posargs)


@nox.session
def lint(session: nox.Session) -> None:
    """Run ruff linter."""
    session.install("ruff")
    session.run("ruff", "check", ".")


@nox.session
def format_check(session: nox.Session) -> None:
    """Check code formatting with ruff."""
    session.install("ruff")
    session.run("ruff", "format", "--check", ".")
