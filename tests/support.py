"""Shared test helpers for the OpenSpec-Graph test suite.

Only genuinely-duplicated helpers live here. Tailored per-test fixture *variants*
( GOOD_HARNESS, MAKEFILE, etc.) stay inline in the test modules that use them,
because each variant asserts behavior specific to its content.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def supports_symlinks() -> bool:
    """Whether this process can create a filesystem symlink right now.

    Windows requires either Administrator rights or Developer Mode enabled
    (SeCreateSymbolicLinkPrivilege) to create any symlink at all, unlike
    POSIX where an unprivileged user always can -- a capability probe, not a
    bare ``sys.platform`` check, so a Windows box that *does* have one of
    those enabled still runs the tests this guards.
    """
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "target"
        target.write_text("")
        try:
            (Path(td) / "link").symlink_to(target)
        except (OSError, NotImplementedError):
            # OSError: the common case (Windows without the privilege).
            # NotImplementedError: Path.symlink_to()'s own fallback when
            # os.symlink doesn't exist on this platform at all -- letting
            # this one escape would crash the *importing* test module at
            # collection time (see the module-level probes in
            # test_witness.py/test_graft.py), the exact all-or-nothing
            # failure this capability probe exists to avoid.
            return False
        return True


def write_spec(repo: Path, change: str, capability: str, body: str) -> Path:
    """Write a spec body into ``openspec/changes/<change>/specs/<capability>/spec.md``."""
    path = repo / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit encoding matches every read/write in openspec_graph itself
    # (parse.py, detect.py, scaffold.py all pass encoding="utf-8") -- without
    # it, Path.write_text's platform-default encoding (e.g. cp1252 on
    # Windows) can't represent arbitrary non-ASCII spec content and raises
    # UnicodeEncodeError before the CLI under test ever runs.
    path.write_text(body, encoding="utf-8")
    return path


def run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the planlint CLI against ``repo`` and return the completed process.

    Injects ``COVERAGE_PROCESS_START`` so this subprocess's coverage is
    tracked, not just the parent test process's -- pytest-cov's own
    auto-installed subprocess hook (a .pth file in site-packages, active
    whenever this env var is set) reads it, no project-specific hook file
    needed. A caller-supplied ``env`` value for the same key always wins,
    never overridden.
    """
    subprocess_env = dict(os.environ if env is None else env)
    subprocess_env.setdefault("COVERAGE_PROCESS_START", str(_PYPROJECT))
    return subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--target", str(repo), *args],
        capture_output=True, text=True, check=False, env=subprocess_env,
        # cli.py's main() always forces its own stdout/stderr to UTF-8
        # (Defect D fix), regardless of the child's ambient encoding -- so
        # the parent side must decode as UTF-8 too, not whatever
        # locale.getpreferredencoding() would otherwise pick (e.g. cp1252 on
        # Windows), or non-ASCII content round-trips as mojibake here even
        # though the child emitted it correctly.
        encoding="utf-8",
    )
