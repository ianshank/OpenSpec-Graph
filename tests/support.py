"""Shared test helpers for the OpenSpec-Graph test suite.

Only genuinely-duplicated helpers live here. Tailored per-test fixture *variants*
( GOOD_HARNESS, MAKEFILE, etc.) stay inline in the test modules that use them,
because each variant asserts behavior specific to its content.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def write_spec(repo: Path, change: str, capability: str, body: str) -> Path:
    """Write a spec body into ``openspec/changes/<change>/specs/<capability>/spec.md``."""
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the specgraph CLI against ``repo`` and return the completed process."""
    return subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--target", str(repo), *args],
        capture_output=True, text=True, check=False, env=env,
    )
