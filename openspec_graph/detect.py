"""Detect a target repository's stack, gates, thresholds, and OpenSpec dialect.

Nothing here writes. Detection is read-only by contract so that `planlint detect`
is always safe to run against an unfamiliar clone.
"""

from __future__ import annotations

import configparser
import dataclasses
import json
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from . import dialect_card, machinery, witness

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

_MAKE_TARGET = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:(?!=)", re.MULTILINE)
_INV_ID = re.compile(r"\bINV-\d+\b")
_ADR_ID = re.compile(r"\bADR-\d+\b")
# A markdown heading line ("# Title", "## Title", ...) -- used to prefer an
# ADR file's own title over an earlier body reference to a different ADR
# when picking its declared id (see _adrs()).
_HEADING_LINE = re.compile(r"^#+[ \t]+\S.*$", re.MULTILINE)
_FAIL_UNDER = re.compile(r"^\s*fail_under\s*=\s*(\d+)", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class ThresholdSource:
    """Where a coverage floor actually lives in this repo."""

    locator: str
    value: int | None

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
        try:
            return str(self.adr_source.relative_to(self.root))
        except ValueError:
            return self.adr_source.name

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
                str(self.invariant_source.relative_to(self.root))
                if self.invariant_source
                else None
            ),
            "invariant_ids": list(self.invariant_ids),
            "has_project_md": self.has_project_md,
            "make_target_confidence": self.make_target_confidence,
            "make_unresolved_count": self.make_unresolved_count,
            "adr_source": (
                str(self.adr_source.relative_to(self.root)) if self.adr_source else None
            ),
            "adr_ids": list(self.adr_ids),
        }

    def to_card(self) -> dict[str, object]:
        """A stable, portable snapshot for CP-2's `detect --format json`/`--diff`.

        Deliberately narrower than as_dict(): excludes every absolute-path
        field (`root`, and `openspec_root` -- always exactly `root /
        "openspec"` when set, so its presence/absence survives as
        `has_openspec_root` without losing information), since an absolute
        path differs across every checkout/machine/CI run and would make a
        `--diff` report constant false "drift" rather than real convention
        drift. An explicit dict literal, not as_dict() with keys deleted,
        so the exact field set is self-documenting here.
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
    text, _ = machinery.strip_define_blocks(text)
    skip = {".PHONY", ".DEFAULT_GOAL", ".SUFFIXES"}
    targets = [t for t in _MAKE_TARGET.findall(text) if t not in skip]
    return tuple(sorted(set(targets)))


def _make_target_facts(root: Path) -> machinery.MakefileFacts:
    makefile = root / "Makefile"
    if not makefile.exists():
        return machinery.MakefileFacts((), False, False, 0)
    text = makefile.read_text(encoding="utf-8", errors="replace")
    facts = machinery.parse_makefile(text)
    if facts.confidence == "low":
        # Widen, never replace: structural parsing found real targets too,
        # and a target it resolved correctly must not be lost because
        # something *else* in the file (an include, a conditional) it
        # couldn't fully resolve. AC-MP-4: never weaken G004, only remove
        # false positives.
        widened = tuple(sorted(set(facts.targets) | set(_legacy_make_targets(text))))
        facts = dataclasses.replace(facts, targets=widened)
    return facts


def _read_ini_fail_under(path: Path, section: str) -> int | None:
    """Read an integer fail_under from an INI-style coverage config section.

    None if the file is absent, unparsable, or lacks the key -- never raises,
    matching this module's fail-quiet-and-move-on style for optional config.
    """
    if not path.exists():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return None
    if not parser.has_option(section, "fail_under"):
        return None
    try:
        return parser.getint(section, "fail_under")
    except ValueError:
        return None


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
        try:
            data = json.loads(policy.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        coverage = data.get("coverage")
        if isinstance(coverage, dict) and isinstance(coverage.get("lines"), int):
            rel = policy.relative_to(root)
            return ThresholdSource(f"{rel}:coverage.lines", coverage["lines"])

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        match = _FAIL_UNDER.search(pyproject.read_text(encoding="utf-8", errors="replace"))
        if match:
            return ThresholdSource(
                "pyproject.toml:[tool.coverage.report].fail_under", int(match.group(1))
            )

    # coverage.py's own convention: bare [report] in .coveragerc, but
    # namespaced [coverage:report] in setup.cfg (to avoid colliding with
    # other tools' sections there) -- different section names, not the same.
    coveragerc = root / ".coveragerc"
    value = _read_ini_fail_under(coveragerc, "report")
    if value is not None:
        return ThresholdSource(f"{coveragerc.relative_to(root)}:[report].fail_under", value)

    setup_cfg = root / "setup.cfg"
    value = _read_ini_fail_under(setup_cfg, "coverage:report")
    if value is not None:
        return ThresholdSource(f"{setup_cfg.relative_to(root)}:[coverage:report].fail_under", value)

    return None


def _invariants(root: Path) -> tuple[Path | None, tuple[str, ...]]:
    for rel in INVARIANT_SOURCES:
        path = root / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # An untrusted target repo's candidate may exist but be
            # unreadable (permission-denied, a broken symlink `exists()`
            # didn't catch, etc.) -- treat it like any other non-match
            # rather than crashing every CLI verb that calls detect.profile().
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
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    # glob() lists directory entries by name pattern only --
                    # a dangling symlink still matches "*.md" but can't be
                    # read. Skip it like any other non-declaring file
                    # instead of crashing every CLI verb that calls
                    # detect.profile() (adversarial review finding on PR #13).
                    continue
                declared = _declared_adr_id(text)
                if declared:
                    ids_list.append(declared)
            ids = sorted(set(ids_list), key=lambda s: (int(s.split("-")[1]), s))
        elif path.is_file():
            # A single index file is itself a declaration list by
            # convention (mirrors _invariants()'s CONTRACT.md assumption),
            # so every mention is a real declaration -- scanning the whole
            # file, not just its first match, is correct here.
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            ids = sorted(
                set(_ADR_ID.findall(text)),
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
    ``mixed``     -- both appear across the repo, which is itself a finding.
    ``unknown``   -- no spec files, or neither marker present.
    """
    upstream = harness = 0
    for path in spec_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "## ADDED Requirements" in text or "#### Scenario:" in text:
            upstream += 1
        if "## Acceptance Criteria" in text and re.search(r"\bAC-[A-Z]{2,}-\d+\b", text):
            harness += 1
    if upstream and harness:
        return "mixed"
    if upstream:
        return "upstream"
    if harness:
        return "harness"
    return "unknown"


def find_spec_files(openspec_root: Path) -> list[Path]:
    return sorted(openspec_root.glob("changes/*/specs/*/spec.md"))


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
            ["git", "rev-parse", "HEAD"],
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
    spec_files = find_spec_files(openspec_root) if has_openspec else []
    change_dirs = (
        tuple(sorted(p for p in (openspec_root / "changes").glob("*") if p.is_dir()))
        if has_openspec and (openspec_root / "changes").is_dir()
        else ()
    )
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
        dialect=detect_dialect(spec_files),
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
    )
