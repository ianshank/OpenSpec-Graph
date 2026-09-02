"""Shared pytest fixtures.

Deliberately minimal: this repository keeps tailored fixtures inline in the
module that uses them (see ``tests/support.py``'s note), so only genuinely
cross-cutting state belongs here.
"""

from __future__ import annotations

import pytest

from openspec_graph import cli


@pytest.fixture(autouse=True)
def _reset_version_cache() -> None:
    """Drop the memoized package-version lookup around every test.

    ``cli._package_version`` is cached so that one CLI run performs one
    metadata lookup and therefore prints at most one ambiguous-environment
    warning (R-FE-8) — argparse resolves it when the parser is built, and
    ``cmd_validate`` needs the same value again for the findings envelope's
    ``tool_version``.

    In-process tests that patch ``importlib.metadata`` would otherwise read a
    value memoized by whichever test ran first, making them pass or fail on
    execution order. Clearing on both sides means no test inherits another's
    resolved version, and none leaks its own.
    """
    cli._package_version.cache_clear()
    yield
    cli._package_version.cache_clear()
