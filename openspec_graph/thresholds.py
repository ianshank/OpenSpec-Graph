"""Coverage-floor discovery: the locators, the scanner, and the number.

Split out of ``detect.py`` as its own responsibility: which files a coverage
floor may live in, how each is read without ever guessing, and what counts
as a number. Pure, stdlib-only, no subprocess. ``detect`` re-exports every
public name here (and the two private ones its tests use), so
``detect.as_threshold_number``, ``detect.scoped_fail_under``,
``detect.COVERAGE_REPORT_TABLE`` and ``detect.ThresholdSource`` keep working.

A line scanner rather than ``tomllib`` throughout: ``tomllib`` is 3.11+ and
this package has no runtime dependencies, so a version-dependent parser
would make the dialect card differ across the CI matrix (DEC-TC-002).
"""

from __future__ import annotations

import configparser
import dataclasses
import json
import logging
import math
import re
from pathlib import Path

from . import machinery
from .repo_io import read_text_or_none, to_posix_relative

__all__ = [
    "COVERAGE_REPORT_TABLE",
    "THRESHOLD_MAX",
    "THRESHOLD_MIN",
    "ThresholdSource",
    "as_threshold_number",
    "find_threshold",
    "read_ini_fail_under",
    "scoped_fail_under",
]

logger = logging.getLogger("planlint.detect")


# A TOML table header (`[tool.coverage.report]`, or the array-of-tables
# `[[x]]` form), with an optional trailing comment. Whitespace inside the
# brackets is tolerated and stripped by the caller.
_TOML_TABLE = re.compile(r"^\s*\[\[?([^\[\]]+)\]\]?\s*(?:#.*)?$")

# `fail_under = <number>`, anchored to a whole line so a key mentioned inside
# a string or comment cannot match. Accepts a decimal fraction: coverage.py
# itself accepts a float floor, and truncating one silently *loosens* the
# gate being reported (85.5 read as 85).
_TOML_FAIL_UNDER = re.compile(r"^\s*fail_under\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(?:#.*)?$")

# The one TOML table a pyproject.toml coverage floor may legitimately live in.
COVERAGE_REPORT_TABLE = "tool.coverage.report"

# The only spelling of a coverage floor this module accepts from text: ASCII
# digits with an optional decimal fraction. Deliberately narrower than
# float()'s grammar, which also takes "1e2", "1_000", "-5", "nan", full-width
# and Arabic-Indic digits -- none of which coverage.py's own config accepts,
# and any of which would let a stray string become a floor W002 then compares
# real witness coverage against.
_THRESHOLD_LITERAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")

# A coverage floor is a percentage. Anything outside this range is not one,
# whatever a config file claims.
THRESHOLD_MIN, THRESHOLD_MAX = 0, 100

def as_threshold_number(raw: object, *, accept_str: bool = True) -> int | float | None:
    """Coerce a detected coverage floor to a number, or ``None``.

    Returns an ``int`` for an integral value and a ``float`` only for a real
    fraction, so an existing integer floor keeps rendering as ``90`` rather
    than ``90.0`` -- the dialect card is a byte-stability contract (AC-DC-1)
    and a saved ``detect --diff`` baseline must not report drift purely
    because this function started widening the type.

    Rejects: booleans (``True`` is an ``int`` in Python); non-finite floats;
    anything outside ``0..100``; and, when ``accept_str`` is false, any string
    at all -- the JSON policy path takes numbers only, as it always did, so a
    quoted ``"90"`` there stays a misconfiguration rather than becoming a
    floor. String input is matched against :data:`_THRESHOLD_LITERAL`, not
    handed to ``float()``. Every rejection is logged at debug level: "why did
    planlint not see my floor?" is the question this module exists to answer.
    """
    if isinstance(raw, bool):
        logger.debug("threshold: rejected boolean %r as a floor", raw)
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    elif isinstance(raw, str):
        if not accept_str:
            logger.debug("threshold: rejected quoted string %r; this locator takes a number", raw)
            return None
        literal = raw.strip()
        if not _THRESHOLD_LITERAL.fullmatch(literal):
            logger.debug("threshold: rejected %r; not a plain decimal", raw)
            return None
        value = float(literal)
    else:
        logger.debug("threshold: rejected %r (%s) as a floor", raw, type(raw).__name__)
        return None
    if not math.isfinite(value) or not THRESHOLD_MIN <= value <= THRESHOLD_MAX:
        logger.debug(
            "threshold: rejected %r; a coverage floor is a percentage in %d..%d",
            raw, THRESHOLD_MIN, THRESHOLD_MAX,
        )
        return None
    return int(value) if value.is_integer() else value

# TOML multi-line string delimiters. A line inside one of these is data, not
# a key, however much it looks like `fail_under = 42` -- and
# `[tool.coverage.report]` is exactly where coverage.py's free-text
# `exclude_lines`/`exclude_also` lists live, so this is the realistic case.
_ML_STRING_DELIMS = ('"""', "'''")

def _normalise_table_name(raw: str) -> str:
    """``[ tool . "coverage" . report ]`` -> ``tool.coverage.report``.

    Handles whitespace around dots and simple quoted segments. A quoted
    segment that itself contains a dot is not handled and is a documented
    limit (docs/next-steps.md 7a).
    """
    return ".".join(seg.strip().strip("\"'") for seg in raw.split("."))

def scoped_fail_under(text: str, table: str) -> int | float | None:
    """``fail_under`` declared under ``[table]`` in TOML ``text``, or ``None``.

    A deliberate line scanner rather than ``tomllib``: ``tomllib`` is 3.11+,
    this package supports 3.10, and it declares **zero** runtime dependencies,
    so a ``tomli`` backport is not available to fall back on. Choosing the
    parser by interpreter version would make detection behave differently
    across the 3.10-3.13 CI matrix, breaking the byte-identical-output
    contract this module is held to; one scanner on every version keeps that
    contract intact.

    Replaces a whole-file ``^\\s*fail_under`` regex that matched the key under
    *any* table and then reported it under a locator naming
    ``[tool.coverage.report]`` -- so a floor belonging to an unrelated tool was
    attributed to a table that did not exist, and G003 compared spec prose
    against a number from somewhere else entirely.
    """
    current = ""
    elsewhere: list[str] = []
    in_ml_string = False
    array_depth = 0
    for line in machinery.strip_bom(text).splitlines():
        stripped = line.strip()
        # Multi-line strings: a line that opens (or closes) one toggles the
        # state; everything inside is opaque. Counting delimiters per line
        # handles the `key = """` opener, the bare `"""` closer, and a
        # one-line `"""x"""` (even count, no toggle) alike.
        delims = sum(stripped.count(d) for d in _ML_STRING_DELIMS)
        if in_ml_string:
            if delims % 2:
                in_ml_string = False
            continue
        if delims % 2:
            in_ml_string = True
            continue
        # Multi-line arrays: `key = [` without its `]` opens one; a closing
        # `]` on a later line ends it. Lines inside are elements, not keys
        # and not table headers, so `[1, 2]` as an element cannot reset the
        # current table.
        if array_depth:
            array_depth += stripped.count("[") - stripped.count("]")
            continue
        header = _TOML_TABLE.match(line)
        if header:
            # `[[x]]` is an array of tables -- a different construct, and never
            # the one holding a coverage floor. Scope it out rather than
            # mistaking it for `[x]`.
            current = "" if stripped.startswith("[[") else _normalise_table_name(header.group(1))
            continue
        if "=" in stripped and stripped.count("[") > stripped.count("]"):
            array_depth = stripped.count("[") - stripped.count("]")
            continue
        found = _TOML_FAIL_UNDER.match(line)
        if not found:
            continue
        if current == table:
            return as_threshold_number(found.group(1))
        # Remember, don't return: the answer to "why did planlint not see my
        # floor?" is usually "it is under a different table", and that is
        # only sayable if the scan kept looking rather than stopping here.
        elsewhere.append(current or "<top level>")
    if elsewhere:
        logger.debug(
            "threshold: fail_under found under %s, not under [%s]; ignored",
            ", ".join(f"[{t}]" for t in elsewhere),
            table,
        )
    return None


@dataclasses.dataclass(frozen=True)
class ThresholdSource:
    """Where a coverage floor actually lives in this repo."""

    locator: str
    # `float` only ever for a genuinely fractional floor -- see
    # as_threshold_number() for why an integral value stays an `int`.
    value: int | float | None

    def as_dict(self) -> dict[str, object]:
        return {"locator": self.locator, "value": self.value}


def read_ini_fail_under(path: Path, section: str) -> int | float | None:
    """Read a fail_under floor from an INI-style coverage config section.

    None if the file is absent, unparsable, or lacks the key -- never raises,
    matching this module's fail-quiet-and-move-on style for optional config.
    Reads the raw string and coerces via :func:`as_threshold_number` rather
    than ``parser.getint``, which rejects the fractional floor coverage.py
    itself accepts and would silently report "no floor detected" for it.
    """
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        # utf-8-sig for the same reason every other read here uses it: a
        # BOM-prefixed `.coveragerc` otherwise reaches configparser as
        # "﻿[report]", raises MissingSectionHeaderError, and the floor
        # silently reads as absent -- the class of defect this file exists to
        # close.
        parser.read(path, encoding="utf-8-sig")
    except (configparser.Error, OSError) as exc:
        logger.debug("threshold: %s could not be parsed: %s", path, exc)
        return None
    if not parser.has_option(section, "fail_under"):
        logger.debug("threshold: %s has no fail_under under [%s]", path.name, section)
        return None
    return as_threshold_number(parser.get(section, "fail_under"))

def find_threshold(root: Path) -> ThresholdSource | None:
    """Find the coverage floor. Order matters: an explicit governance policy wins."""
    policy_candidates = [
        root / "harness" / "shared" / "governance-policy.json",
        root / "governance-policy.json",
        root / ".governance" / "governance-policy.json",
    ]
    for policy in policy_candidates:
        if not policy.exists():
            continue
        raw = read_text_or_none(policy, "threshold")
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.debug("threshold: %s is not valid JSON: %s", policy, exc)
            continue
        coverage = data.get("coverage") if isinstance(data, dict) else None
        if isinstance(coverage, dict):
            # Numbers only, as this locator always required: a quoted "90" in
            # a policy file is a misconfiguration, not a floor.
            lines = as_threshold_number(coverage.get("lines"), accept_str=False)
            if lines is not None:
                rel = to_posix_relative(policy, root)
                logger.debug("threshold: found coverage.lines in %s", rel)
                return ThresholdSource(f"{rel}:coverage.lines", lines)
        logger.debug("threshold: %s has no numeric coverage.lines", policy)

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = read_text_or_none(pyproject, "threshold")
        if text is not None:
            value = scoped_fail_under(text, COVERAGE_REPORT_TABLE)
            if value is not None:
                logger.debug(
                    "threshold: found fail_under=%s under [%s]", value, COVERAGE_REPORT_TABLE
                )
                return ThresholdSource(
                    f"pyproject.toml:[{COVERAGE_REPORT_TABLE}].fail_under", value
                )
            logger.debug(
                "threshold: pyproject.toml has no fail_under under [%s]", COVERAGE_REPORT_TABLE
            )

    # coverage.py's own convention: bare [report] in .coveragerc, but
    # namespaced [coverage:report] in setup.cfg (to avoid colliding with
    # other tools' sections there) -- different section names, not the same.
    coveragerc = root / ".coveragerc"
    value = read_ini_fail_under(coveragerc, "report")
    if value is not None:
        rel = to_posix_relative(coveragerc, root)
        return ThresholdSource(f"{rel}:[report].fail_under", value)

    setup_cfg = root / "setup.cfg"
    value = read_ini_fail_under(setup_cfg, "coverage:report")
    if value is not None:
        rel = to_posix_relative(setup_cfg, root)
        return ThresholdSource(f"{rel}:[coverage:report].fail_under", value)

    # The highest-value diagnostic in the module. A repo with no detected floor
    # gets G003 findings phrased against "the coverage floor" with no way to
    # see which six locations were consulted, so the obvious next question --
    # "where should I put it?" -- had no answer anywhere in the output.
    logger.debug(
        "threshold: no floor found under %s; tried %s, then pyproject.toml, "
        ".coveragerc [report], setup.cfg [coverage:report]",
        root,
        [to_posix_relative(c, root) for c in policy_candidates],
    )
    return None
