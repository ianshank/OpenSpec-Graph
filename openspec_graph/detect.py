"""Detect a target repository's stack, gates, thresholds, and OpenSpec dialect.

Nothing here writes. Detection is read-only by contract so that `planlint detect`
is always safe to run against an unfamiliar clone.
"""

from __future__ import annotations

import configparser
import dataclasses
import json
import logging
import math
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from . import dialect_card, machinery, witness
from .parse_semantics import is_harness_marked, is_speckit_marked, is_upstream_marked

MANIFESTS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
    "node": ("package.json",),
    "rust": ("Cargo.toml",),
    "go": ("go.mod",),
    "jvm": ("pom.xml", "build.gradle", "build.gradle.kts"),
}

# Where invariant/contract IDs are conventionally declared, most specific first.
INVARIANT_SOURCES: tuple[str, ...] = (
    "harness/CONTRACT.md",
    "CONTRACT.md",
    "HARNESS_SPEC.md",
    "docs/CONTRACT.md",
    "docs/HARNESS_SPEC.md",
    "AGENTS.md",
)

# Where ADR (architecture decision record) files conventionally live, most
# specific first. A directory candidate (the dominant real-world convention:
# one numbered file per decision) is tried before a single-file index
# fallback. Ids are still extracted by regex-scanning each file's own text
# (mirroring _invariants()'s proven mechanism), never parsed from filenames --
# avoids a zero-padding mismatch between a directory's "0007-title.md" and a
# spec's bare "ADR-7" citation.
ADR_SOURCES: tuple[str, ...] = (
    "docs/adr",
    "docs/architecture/decisions",
    "docs/decisions",
    "adr",
    "docs/ADR.md",
)

# Module logger. Detection is where every "why did planlint not see my X?"
# question is actually answered, and until now it answered none of them: the
# candidate locations tried, the ones rejected and why, and the per-file
# dialect votes were all discarded before anything could observe them.
#
# No handler is attached here. `log.configure()` (called from `cli.main`) owns
# the stderr handler and the propagate=False that keeps records off stdout, so
# a library consumer importing `detect.profile()` directly gets the standard
# no-handler silence rather than output this module decided to emit.
logger = logging.getLogger("planlint.detect")

_MAKE_TARGET = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:(?!=)", re.MULTILINE)
_INV_ID = re.compile(r"\bINV-\d+\b")
_ADR_ID = re.compile(r"\bADR-\d+\b")
# A markdown heading line ("# Title", "## Title", ...) -- used to prefer an
# ADR file's own title over an earlier body reference to a different ADR
# when picking its declared id (see _adrs()).
_HEADING_LINE = re.compile(r"^#+[ \t]+\S.*$", re.MULTILINE)
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


@dataclasses.dataclass(frozen=True)
class StackProfile:
    root: Path
    languages: tuple[str, ...]
    make_targets: tuple[str, ...]
    openspec_root: Path | None
    change_dirs: tuple[Path, ...]
    dialect: str
    threshold: ThresholdSource | None
    invariant_source: Path | None
    invariant_ids: tuple[str, ...]
    has_project_md: bool
    make_target_confidence: str = "high"
    make_unresolved_count: int = 0
    adr_source: Path | None = None
    adr_ids: tuple[str, ...] = ()
    witnesses: tuple[witness.Witness, ...] = ()
    current_sha: str | None = None
    speckit_root: Path | None = None
    feature_dirs: tuple[Path, ...] = ()

    @property
    def invariant_source_name(self) -> str:
        """Human-readable name of the invariant source, or a generic
        fallback when none is detected -- shared by G005 (rules_generic.py)
        and G006 (rules.py) so the two can't independently drift on wording."""
        return self.invariant_source.name if self.invariant_source else "the contract"

    @property
    def adr_source_name(self) -> str:
        """Human-readable name of the ADR source, or a generic fallback when
        none is detected -- shared by G008 (rules_generic.py) and G009
        (rules.py) so the two can't independently drift on wording. Uses the
        root-relative path, not invariant_source_name's bare .name, because
        ADR candidates are nested directories (docs/adr,
        docs/architecture/decisions) where a bare name is ambiguous in a way
        CONTRACT.md's flat, near-root file candidates never were."""
        if not self.adr_source:
            return "the ADR log"
        return to_posix_relative(self.adr_source, self.root)

    def as_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "languages": list(self.languages),
            "make_targets": list(self.make_targets),
            "openspec_root": str(self.openspec_root) if self.openspec_root else None,
            "change_dirs": [d.name for d in self.change_dirs],
            "dialect": self.dialect,
            "threshold": self.threshold.as_dict() if self.threshold else None,
            "invariant_source": (
                to_posix_relative(self.invariant_source, self.root)
                if self.invariant_source
                else None
            ),
            "invariant_ids": list(self.invariant_ids),
            "has_project_md": self.has_project_md,
            "make_target_confidence": self.make_target_confidence,
            "make_unresolved_count": self.make_unresolved_count,
            "adr_source": (
                to_posix_relative(self.adr_source, self.root) if self.adr_source else None
            ),
            "adr_ids": list(self.adr_ids),
            "speckit_root": str(self.speckit_root) if self.speckit_root else None,
            "feature_dirs": [d.name for d in self.feature_dirs],
        }

    def to_card(self) -> dict[str, object]:
        """A stable, portable snapshot for CP-2's `detect --format json`/`--diff`.

        Deliberately narrower than as_dict(): excludes every absolute-path
        field (`root`, `openspec_root` -- always exactly `root /
        "openspec"` when set, so its presence/absence survives as
        `has_openspec_root` without losing information -- and `speckit_root`
        likewise as `has_speckit_root`, always exactly `root / "specs"` when
        set), since an absolute path differs across every checkout/machine/CI
        run and would make a `--diff` report constant false "drift" rather
        than real convention drift. An explicit dict literal, not as_dict()
        with keys deleted, so the exact field set is self-documenting here.
        """
        base = self.as_dict()
        return {
            "schema_version": dialect_card.SCHEMA_VERSION,
            "languages": base["languages"],
            "make_targets": base["make_targets"],
            "has_openspec_root": base["openspec_root"] is not None,
            "change_dirs": base["change_dirs"],
            "dialect": base["dialect"],
            "threshold": base["threshold"],
            "invariant_source": base["invariant_source"],
            "invariant_ids": base["invariant_ids"],
            "has_project_md": base["has_project_md"],
            "make_target_confidence": base["make_target_confidence"],
            "make_unresolved_count": base["make_unresolved_count"],
            "adr_source": base["adr_source"],
            "adr_ids": base["adr_ids"],
            "has_speckit_root": base["speckit_root"] is not None,
            "feature_dirs": base["feature_dirs"],
        }


def _languages(root: Path) -> tuple[str, ...]:
    found = [
        lang
        for lang, names in MANIFESTS.items()
        if any((root / n).exists() for n in names)
    ]
    return tuple(sorted(found))


def _legacy_make_targets(text: str) -> tuple[str, ...]:
    """Pre-machinery.py regex extraction. Kept, not deleted: R-MP-3 mandates
    it as the fallback source when structural parsing can't fully resolve a
    Makefile (see _make_target_facts).

    define...endef block bodies are stripped first via
    machinery.strip_define_blocks -- the same O(n) line-scan
    parse_makefile uses, not a second, separately-buggy implementation:
    their bodies are opaque replacement text, and a body line containing a
    colon (e.g. "Usage: ...") would otherwise regex-match as a fabricated
    target, closed here too since a low-confidence Makefile (a define
    block included) widens using exactly this fallback."""
    # strip_bom for the same reason parse_makefile does it, and symmetrically:
    # this fallback failed *differently* on a BOM (its `^[a-zA-Z]` anchor
    # cannot match U+FEFF, so it silently dropped the first target instead of
    # fabricating a mangled one). The two parsers must not diverge on BOM
    # handling any more than they may on define/endef handling.
    text, _ = machinery.strip_define_blocks(machinery.strip_bom(text))
    skip = {".PHONY", ".DEFAULT_GOAL", ".SUFFIXES"}
    targets = [t for t in _MAKE_TARGET.findall(text) if t not in skip]
    return tuple(sorted(set(targets)))


def _make_target_facts(root: Path) -> machinery.MakefileFacts:
    makefile = root / "Makefile"
    if not makefile.exists():
        return machinery.MakefileFacts((), False, False, 0)
    text = read_text_or_none(makefile, "make_targets")
    if text is None:
        # Exists but unreadable (a directory named `Makefile`, a permission
        # denial, a dangling symlink). "No Makefile" is the safe reading: with
        # no targets, G004 returns early rather than manufacturing findings.
        return machinery.MakefileFacts((), False, False, 0)
    facts = machinery.parse_makefile(text)
    if facts.confidence == "low":
        # Widen, never replace: structural parsing found real targets too,
        # and a target it resolved correctly must not be lost because
        # something *else* in the file (an include, a conditional) it
        # couldn't fully resolve. AC-MP-4: never weaken G004, only remove
        # false positives.
        legacy = set(_legacy_make_targets(text))
        added = sorted(legacy - set(facts.targets))
        if added:
            logger.debug(
                "make_targets: structural parse is low-confidence; regex fallback added %s",
                added,
            )
        widened = tuple(sorted(set(facts.targets) | legacy))
        facts = dataclasses.replace(facts, targets=widened)
    return facts


def _read_ini_fail_under(path: Path, section: str) -> int | float | None:
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


def _threshold(root: Path) -> ThresholdSource | None:
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
    value = _read_ini_fail_under(coveragerc, "report")
    if value is not None:
        rel = to_posix_relative(coveragerc, root)
        return ThresholdSource(f"{rel}:[report].fail_under", value)

    setup_cfg = root / "setup.cfg"
    value = _read_ini_fail_under(setup_cfg, "coverage:report")
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


def _invariants(root: Path) -> tuple[Path | None, tuple[str, ...]]:
    for rel in INVARIANT_SOURCES:
        path = root / rel
        if not path.exists():
            continue
        # An untrusted target repo's candidate may exist but be unreadable
        # (permission-denied, a directory, a broken symlink `exists()` didn't
        # catch) -- read_text_or_none treats it like any other non-match
        # rather than crashing every CLI verb that calls detect.profile().
        text = read_text_or_none(path, "invariants")
        if text is None:
            continue
        ids = sorted(
            set(_INV_ID.findall(text)),
            # String tie-breaker: two ids that parse to the same integer
            # (e.g. "INV-1" and "INV-01") would otherwise order by
            # hash-seed-dependent set iteration -- unlikely, but the
            # dialect card's byte-stability promise (AC-DC-1) shouldn't
            # rest on an assumption that never holds.
            key=lambda s: (int(s.split("-")[1]), s),
        )
        if ids:
            return path, tuple(ids)
    return None, ()


def _declared_adr_id(text: str) -> str | None:
    """Pick the one ADR id a file's own text *declares*, as opposed to
    merely *cites* in passing ("Supersedes ADR-99", "Related: ADR-1").

    Prefer the first id that appears on a markdown heading line -- a
    decision record's own title -- since a title is a far more reliable
    declaration marker than raw position in the file: a preamble,
    front-matter, or "Related decisions" line can otherwise precede the
    file's own heading and get mistaken for the declaration (found by
    adversarial review after the original "just take the first mention"
    fix, itself a Copilot review finding on PR #13). Fall back to the
    first mention anywhere only when no heading contains an id at all, so
    a file that doesn't follow the heading convention still yields its
    one prior candidate rather than silently dropping to zero ids.
    """
    for heading in _HEADING_LINE.finditer(text):
        match = _ADR_ID.search(heading.group())
        if match:
            return match.group()
    first = _ADR_ID.search(text)
    return first.group() if first else None


def _adrs(root: Path) -> tuple[Path | None, tuple[str, ...]]:
    for rel in ADR_SOURCES:
        path = root / rel
        if path.is_dir():
            # Flat, non-recursive: matches the dominant flat-file ADR
            # convention. A nested docs/adr/superseded/ subfolder is a
            # known, accepted coverage limitation (mirrors
            # INVARIANT_SOURCES' own fixed-candidate-list limitation), not
            # a bug.
            #
            # One declared id per file, via _declared_adr_id() -- not every
            # mention in its body. Scanning the whole file for every
            # occurrence would wrongly promote a citation to a second
            # declaration, letting G008 accept a citation to an ADR that
            # was never really declared, or G009 report it as an orphan
            # that was never really declared either.
            ids_list: list[str] = []
            for p in sorted(path.glob("*.md")):
                # glob() lists directory entries by name pattern only -- a
                # dangling symlink still matches "*.md" but can't be read.
                # Skip it like any other non-declaring file instead of
                # crashing every CLI verb that calls detect.profile()
                # (adversarial review finding on PR #13).
                text_or_none = read_text_or_none(p, "adr")
                if text_or_none is None:
                    continue
                declared = _declared_adr_id(text_or_none)
                if declared:
                    ids_list.append(declared)
            ids = sorted(set(ids_list), key=lambda s: (int(s.split("-")[1]), s))
        elif path.is_file():
            # A single index file is itself a declaration list by
            # convention (mirrors _invariants()'s CONTRACT.md assumption),
            # so every mention is a real declaration -- scanning the whole
            # file, not just its first match, is correct here.
            index_text = read_text_or_none(path, "adr")
            if index_text is None:
                continue
            ids = sorted(
                set(_ADR_ID.findall(index_text)),
                key=lambda s: (int(s.split("-")[1]), s),
            )
        else:
            continue
        if ids:
            return path, tuple(ids)
    return None, ()


def detect_dialect(spec_paths: list[Path]) -> str:
    """Classify which OpenSpec spec dialect a repo writes.

    ``upstream``  -- ``## ADDED Requirements`` + ``#### Scenario:`` GIVEN/WHEN/THEN.
    ``harness``   -- ``## Acceptance Criteria`` with ``AC-<AREA>-<n>`` + ``_Verified by:_``.
    ``speckit``   -- ``### Functional Requirements`` + ``FR-<n>``, or
                     ``## Success Criteria`` + ``SC-<n>``.
    ``mixed``     -- more than one of the three predicates matches across the
                     repo, which is itself a finding (not an enumerated set of
                     pairwise/triple combinations -- nothing downstream needs
                     finer granularity than "more than one dialect present").
    ``unknown``   -- no spec files, or none of the three predicates matches.

    Marker predicates live in :mod:`parse_semantics`, shared with
    :func:`parse.parse_spec`'s own ``mixed``/``unknown``/``auto``
    pre-resolution -- previously two independently duplicated copies of the
    same marker strings, unified so they can never drift apart.
    """
    upstream = harness = speckit = 0
    votes: dict[str, list[str]] = {"upstream": [], "harness": [], "speckit": []}
    for path in spec_paths:
        text = read_text_or_none(path, "dialect")
        if text is None:
            continue
        if is_upstream_marked(text):
            upstream += 1
            votes["upstream"].append(str(path))
        if is_harness_marked(text):
            harness += 1
            votes["harness"].append(str(path))
        if is_speckit_marked(text):
            speckit += 1
            votes["speckit"].append(str(path))
    present = sum(1 for count in (upstream, harness, speckit) if count)
    if present > 1:
        # The one verdict a user cannot act on without knowing which files
        # disagreed. `validate` prints "more than one spec dialect" and stops;
        # this is the only place the evidence exists.
        logger.debug(
            "dialect: mixed -- upstream=%s harness=%s speckit=%s",
            votes["upstream"], votes["harness"], votes["speckit"],
        )
        return "mixed"
    if upstream:
        return "upstream"
    if harness:
        return "harness"
    if speckit:
        return "speckit"
    return "unknown"


def _dedupe_by_identity(paths: Iterable[Path]) -> list[Path]:
    """One entry per underlying file, keeping the first logical path.

    ``Path.glob()`` follows a *valid* directory symlink, so a
    ``specs/002-alias -> specs/001-foo`` link yields two distinct ``Path``
    entries for the same ``spec.md``. Unfixed, that one spec is parsed twice:
    ``change_dirs``/``feature_dirs`` over-count, ``validate``'s
    ``specs_checked`` over-reports, and ``build_graph`` renders duplicate
    ``FR-001``/``SC-001`` nodes for a single requirement.

    Identity is ``Path.resolve()``, not content: two genuinely separate files
    with identical text are two specs and both must be linted.

    The survivor is the path that *is* its own real path — the real directory,
    not an alias pointing at it. Keeping the first entry in sorted order
    instead would be deterministic but arbitrary, and measurably wrong: with
    ``changes/alias -> changes/real``, "alias" sorts first, so the real
    package became unaddressable by its own name (``--change real`` reported
    "no specs found" while ``--change alias`` passed). Whichever name a
    reviewer would recognise has to be the one that survives.

    Ordering still decides between two aliases that both point elsewhere, so
    the result stays stable across runs for any input.

    A candidate whose real path cannot be determined keeps its logical path
    instead of being dropped. Discovery never silently loses a spec; whether
    it can actually be read is the read guard's decision downstream
    (``parse.SpecReadError``), and a spec that vanished here would pass a gate
    that never saw it.
    """
    by_identity: dict[Path, Path] = {}
    order: list[Path] = []
    for path in paths:
        try:
            identity = path.resolve()
        except OSError as exc:  # pragma: no cover - platform-dependent
            logger.debug("cannot resolve %s (%s); keeping the logical path", path, exc)
            identity = path
        incumbent = by_identity.get(identity)
        if incumbent is None:
            by_identity[identity] = path
            order.append(identity)
            continue
        # Same underlying file. Prefer the real path over an alias; otherwise
        # the incumbent stands, so ordering breaks the remaining ties.
        if incumbent != identity and path == identity:
            logger.debug("preferring real path %s over alias %s", path, incumbent)
            by_identity[identity] = path
        else:
            logger.debug("skipping %s: same file as %s", path, incumbent)
    return [by_identity[identity] for identity in order]


def find_spec_files(openspec_root: Path) -> list[Path]:
    return _dedupe_by_identity(sorted(openspec_root.glob("changes/*/specs/*/spec.md")))


def find_speckit_spec_files(speckit_root: Path) -> list[Path]:
    """``specs/<feature>/spec.md`` -- one segment shallower than
    ``find_spec_files``'s ``changes/*/specs/*/spec.md``, since SpecKit has no
    ``changes/`` nesting at all.

    Content-gated per file, unlike ``find_spec_files``, which is purely
    structural: each candidate must also match ``is_speckit_marked()``.
    ``specs/`` is too common a directory name (OpenAPI, RSpec, JSON-schema
    conventions all use it) to trust structurally alone -- an unrelated
    ``specs/<name>/spec.md`` (a documentation pointer, say) sitting under a
    repo-root ``specs/`` dir must not be swept into discovery and
    force-parsed under the repo's prevailing dialect, where it would fail
    ``validate`` for content it was never meant to be linted as.
    """
    found: list[Path] = []
    skipped: list[str] = []
    for path in _dedupe_by_identity(sorted(speckit_root.glob("*/spec.md"))):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.debug("speckit: cannot read %s: %s", path, exc)
            continue
        if is_speckit_marked(text):
            found.append(path)
        else:
            skipped.append(str(path))
    if skipped:
        # From the outside this is indistinguishable from the file not
        # existing: it simply never appears in `validate`. Naming the dropped
        # candidates is the difference between "planlint ignored my spec" and
        # "my spec is missing the SpecKit markers".
        logger.debug("speckit: %d candidate(s) lack SpecKit markers: %s",
                     len(skipped), skipped)
    return found


def filter_speckit_by_feature(spec_files: Sequence[Path], feature: str) -> list[Path]:
    """Narrow a SpecKit spec-file list to one feature's own ``spec.md``.

    Mirrors ``filter_by_change``'s fixed-position anchor, one level
    shallower: ``specs/<feature>/spec.md`` has no ``changes/`` segment to
    anchor past.
    """
    return [
        p
        for p in spec_files
        if len(p.parts) >= 3 and p.parts[-3] == "specs" and p.parts[-2] == feature
    ]


def filter_by_change(spec_files: Sequence[Path], change: str) -> list[Path]:
    """Narrow a spec-file list to one change package's own specs.

    Single-sourced: both ``cmd_validate`` and ``cmd_graph`` (``--change``)
    use this, rather than each carrying its own copy of the path filter to
    drift apart.

    Anchors on the *fixed* structural position of the
    ``changes/<name>/specs/<capability>/spec.md`` convention (exactly what
    ``find_spec_files`` produces), rather than scanning for the first/any
    ``"changes"`` segment: a forward scan that only stops once it finds a
    "changes" segment *followed by the queried name* -- as an earlier
    version of this function did -- is imprecise the moment a change's own
    name is itself ``"changes"``. That name then reads as a second, bogus
    marker, and the fixed ``"specs"`` segment one slot after it can
    spuriously satisfy a query for an unrelated change also named
    ``"specs"``. Matching a fixed position rather than a repeatable literal
    closes that -- the same imprecision class a plain ``str(p)`` substring
    check has, one level down.
    """
    return [
        p
        for p in spec_files
        if len(p.parts) >= 5
        and p.parts[-5] == "changes"
        and p.parts[-4] == change
        and p.parts[-3] == "specs"
    ]


def _current_sha(root: Path) -> str | None:
    """The target repo's current commit sha, or ``None`` if it can't be
    determined -- the only place ``subprocess`` is used anywhere in
    ``openspec_graph/`` (``DEC-WM-008``/``DEC-WM-009``).

    ``git rev-parse HEAD`` is read-only plumbing that never evaluates
    arbitrary content from the target repo's own tracked files, unlike
    ``make`` (which evaluates ``$(shell ...)`` unconditionally at parse
    time) -- ``DEC-MP-001``'s specific danger doesn't transfer to this call.
    Every failure mode (not a git repo, git not installed, timeout, a
    non-zero exit, unexpected stdout) folds uniformly to ``None`` rather
    than raising -- callers treat "unavailable" as a single case, not a
    grab-bag of exceptions to catch individually.
    """
    try:
        result = subprocess.run(
            # S607: `git` is resolved from PATH deliberately. An absolute path
            # would have to be guessed per platform and per installation, and
            # the argument vector is a fixed literal with no target-controlled
            # input -- see this function's docstring on why DEC-MP-001's
            # shell-injection concern does not transfer to it.
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return None
    return sha


def profile(root: Path) -> StackProfile:
    root = root.resolve()
    openspec_root = root / "openspec"
    has_openspec = openspec_root.is_dir()
    openspec_spec_files = find_spec_files(openspec_root) if has_openspec else []
    # Deduplicated by real-path identity for the same reason the spec-file
    # globs are: a `changes/alias -> changes/real` directory symlink is two
    # entries for one change package, and every count derived from this
    # (`detect`'s own report, the dialect card) would report work that does
    # not exist. Kept as its own glob rather than derived from
    # openspec_spec_files, because a change package with no spec.md yet is
    # still a change package.
    change_dirs = (
        tuple(
            _dedupe_by_identity(
                sorted(p for p in (openspec_root / "changes").glob("*") if p.is_dir())
            )
        )
        if has_openspec and (openspec_root / "changes").is_dir()
        else ()
    )

    speckit_root_candidate = root / "specs"
    speckit_spec_files = (
        find_speckit_spec_files(speckit_root_candidate)
        if speckit_root_candidate.is_dir()
        else []
    )
    has_speckit = bool(speckit_spec_files)
    # Distinct, sorted parent directories of the content-gated spec files --
    # not every structural subdirectory of speckit_root/DEC-SK-002's
    # per-file gate would be undone by falling back to an ungated glob here.
    feature_dirs = tuple(sorted({p.parent for p in speckit_spec_files}))

    invariant_source, invariant_ids = _invariants(root)
    adr_source, adr_ids = _adrs(root)
    make_facts = _make_target_facts(root)
    witnesses = witness.load_witnesses(root)
    # Lazy: detect.profile() runs on every detect/validate/graph call
    # (including this project's own 300+-test suite), and the current sha
    # is meaningless with zero witnesses to compare against -- never even
    # computed in that case (AC-WM-19, DEC-WM-008); validate still fails
    # closed on an empty witness store regardless (AC-WM-9).
    current_sha = _current_sha(root) if witnesses else None
    return StackProfile(
        root=root,
        languages=_languages(root),
        make_targets=make_facts.targets,
        openspec_root=openspec_root if has_openspec else None,
        change_dirs=change_dirs,
        dialect=detect_dialect(list(openspec_spec_files) + speckit_spec_files),
        threshold=_threshold(root),
        invariant_source=invariant_source,
        invariant_ids=invariant_ids,
        has_project_md=(openspec_root / "project.md").exists() if has_openspec else False,
        make_target_confidence=make_facts.confidence,
        make_unresolved_count=make_facts.unresolved_count,
        adr_source=adr_source,
        adr_ids=adr_ids,
        witnesses=witnesses,
        current_sha=current_sha,
        speckit_root=speckit_root_candidate if has_speckit else None,
        feature_dirs=feature_dirs,
    )
