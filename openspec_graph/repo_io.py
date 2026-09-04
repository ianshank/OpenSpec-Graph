"""Read-only filesystem helpers shared by detection and threshold discovery.

Split out of ``detect.py`` (which had grown past eight hundred lines) so the
one read path every optional-config lookup uses, and the portable path
renderer every locator uses, sit in a module with no other responsibility.
Pure, stdlib-only, no subprocess (``detect.py`` remains the package's single
``subprocess`` importer, DEC-WM-009). ``detect`` re-exports both names, so
every existing ``detect.read_text_or_none`` / ``detect.to_posix_relative``
caller is unchanged.
"""

from __future__ import annotations

import logging
from pathlib import Path

__all__ = ["read_text_or_none", "to_posix_relative"]

# Under the "planlint" handler `log.configure()` installs; the name says
# where a record came from without a second handler.
logger = logging.getLogger("planlint.detect")


def to_posix_relative(path: Path, root: Path | None) -> str:
    """``path`` relative to ``root``, forward-slash rendered.

    ``str(path.relative_to(root))``/plain f-string interpolation render with
    the host OS's native separator -- identical to this on POSIX, but
    backslash-separated on Windows, which breaks every consumer that expects
    (or hardcodes, in this project's own test suite) a portable, forward-slash
    relative path. Falls back to ``path.as_posix()`` -- never the
    native-separator ``str(path)`` -- when ``root`` is ``None`` or ``path``
    isn't actually under it; never raises. Shared by graph.py, ledger.py,
    rule_types.py, scaffold.py, and this module's own StackProfile/threshold
    fields, all of which had independently copy-pasted the buggy pattern.
    """
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()

def read_text_or_none(path: Path, what: str) -> str | None:
    """``path``'s text, or ``None`` if it cannot be read.

    Decodes with ``utf-8-sig`` so a UTF-8 BOM is consumed by the codec rather
    than surviving into the first parsed line (see ``machinery.strip_bom``).

    Every optional-config read in this module funnels through here. Three of
    them previously called ``read_text()`` directly after an ``exists()``
    check, which is a time-of-check/time-of-use gap *and* simply wrong for a
    path that exists but is not a regular file: a directory named ``Makefile``
    or ``pyproject.toml`` raised ``IsADirectoryError`` out of
    ``detect.profile()``, crashing every CLI verb with a traceback and exit 1
    (the code reserved for "findings were reported") against a repository
    planlint is only *inspecting*. Returning ``None`` treats it as absent,
    which is the convention ``_invariants``/``_adrs`` already followed and the
    only safe posture for an untrusted target repo.
    """
    # is_file() first, not just a try/except around the read: a FIFO named
    # `Makefile` passes exists(), and open() on it blocks until a writer
    # appears -- detect.profile() would never return, and no exception would
    # ever be raised to catch. Git cannot store a FIFO so a clone is safe,
    # but "safe to point at an unfamiliar tree" is a working-tree promise.
    if not path.is_file():
        logger.debug("%s: %s exists but is not a regular file; treated as absent", what, path)
        return None
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        logger.debug("%s: could not read %s: %s", what, path, exc)
        return None
