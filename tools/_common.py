"""Small shared helpers for the ``tools/`` gate scripts.

These scripts are intentionally dependency-free (stdlib only) so they run in a
bare CI runner. Anything repeated across them lives here so a fix to repo-root
discovery or text reading is made once.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

# Debug logging for the gate scripts, under the CLI's own "planlint" logger
# namespace so one env var covers both.
#
# The env var must be read *here*. `logging.getLogger` inherits nothing from
# openspec_graph.log: that module reads PLANLINT_LOG_LEVEL only inside its own
# configure(), which no tool calls, and tools stay stdlib-only so they cannot
# import it anyway (a gate script must run in a bare CI runner where planlint
# may not be installed). Attaching the name without reading the variable was
# tried first and silently dropped every record while the comment claimed
# otherwise -- so the level is resolved and a handler attached below.
_ENV_VARS = ("PLANLINT_LOG_LEVEL", "SPECGRAPH_LOG_LEVEL")  # legacy name second
logger = logging.getLogger("planlint.tools")


def _configure_from_env() -> None:
    """Set the tools logger's level from the environment, once.

    Idempotent and handler-safe: re-importing this module (tests load these
    scripts by path more than once) must not stack duplicate handlers.
    Records go to stderr, never stdout, because a gate script's stdout is
    parsed by CI and by ``make``.
    """
    raw = ""
    for name in _ENV_VARS:
        raw = os.environ.get(name, "")
        if raw:
            break
    named = logging.getLevelName(raw.upper())
    logger.setLevel(named if isinstance(named, int) else logging.WARNING)
    if not logger.handlers:
        handler = logging.StreamHandler()  # stderr
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


_configure_from_env()

# tools/ sits one level below the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """Return the repository root (the parent of the ``tools/`` directory)."""
    return REPO_ROOT


def read_text(path: Path) -> str:
    """Read a file as UTF-8, returning ``\"\"`` if it is missing.

    Centralizes the ``encoding=\"utf-8\"`` convention used by every gate script
    so encoding is never left to the platform default.
    """
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_pyproject_int(pyproject: Path, section: str, key: str) -> int | None:
    """Read one integer key out of one ``pyproject.toml`` table, stdlib only.

    Hand-rolled rather than via ``tomllib`` because these gate scripts run
    before anything is installed and on the 3.10 leg of the matrix, where the
    stdlib parser does not exist. Section-aware on purpose: a bare search for
    the key would match the same name under any other table.

    The path is an argument rather than :func:`repo_root`, deliberately. The
    coverage gates read the ``pyproject.toml`` of whichever tree they are
    pointed at, so they can be exercised against a synthetic one (see
    ``tests/test_ci_hardening.py``, which writes a floor of 95 into a temp
    directory and asserts the gate honours it). Anchoring at this repository's
    own root would make the gate untestable and would silently ignore the
    config of the tree actually being measured.

    Returns ``None`` when the file, the table, or the key is absent. Callers
    treat that as a misconfiguration and fail loudly; it is never a skip.
    """
    if not pyproject.exists():
        return None
    in_section = False
    pattern = re.compile(rf"{re.escape(key)}\s*=\s*(\d+)")
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == section
            continue
        if not in_section:
            continue
        match = pattern.match(stripped)
        if match:
            return int(match.group(1))
    return None


def write_or_check(path: Path, expected: str, *, write: bool, label: str) -> int:
    """Regenerate ``path`` from ``expected``, or verify it already matches.

    The shared half of every generated-artifact tool here (the rule catalog,
    the plugin manifests): a ``--write`` mode that is the single writer, and a
    ``--check`` mode CI runs to prove the committed file was regenerated. The
    two modes must agree byte-for-byte or the check is theater, which is why
    they read from one ``expected`` string rather than each formatting its own.

    Returns a process exit code: 0 for written or fresh, 1 for stale/missing.
    ``label`` names the make target that regenerates the file, so the failure
    message tells the reader what to run instead of only what is wrong.
    """
    # Display path: repo-relative when the target is inside the repo, absolute
    # otherwise. relative_to() raises on any path outside REPO_ROOT, which a
    # test redirecting the target into a temp directory legitimately does --
    # a generator helper must not require its output to live in this repo.
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(path)
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        changed = read_text(path) != expected
        path.write_text(expected, encoding="utf-8")
        logger.debug("write_or_check: wrote %s (changed=%s)", rel, changed)
        print(f"wrote {rel}" if changed else f"unchanged {rel}")
        return 0

    actual = read_text(path)
    if not actual:
        logger.debug("write_or_check: %s missing or empty", rel)
        print(f"STALE: {rel} is missing or empty; run `{label}`", file=sys.stderr)
        return 1
    if actual != expected:
        logger.debug(
            "write_or_check: %s differs (%d bytes on disk, %d expected)",
            rel, len(actual), len(expected),
        )
        print(f"STALE: {rel} does not match its generator; run `{label}`", file=sys.stderr)
        return 1
    logger.debug("write_or_check: %s is fresh", rel)
    return 0
