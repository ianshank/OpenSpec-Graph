"""Parse an OpenSpec spec document into a dialect-neutral structure.

Both supported dialects reduce to the same shape: a set of normative
requirements, a set of verifiable criteria, and the external references
(make targets, invariant IDs) the document claims.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_STATUS = re.compile(r"\*\*Status:\*\*\s*([A-Za-z-]+)")

# --- harness dialect -------------------------------------------------------
_AC = re.compile(
    r"^-\s*\[( |x|X)\]\s*\*\*(AC-[A-Z]{2,}-\d+)([^:*]*?):\*\*\s*(.+?)\s*$", re.MULTILINE
)
_VERIFIED_BY = re.compile(r"_Verified by:_\s*(.+?)\s*$", re.MULTILINE)
_REQ_DECL = re.compile(r"^-\s*((?:R|C)-[A-Z]{2,}-\d+)\s*:\s*(.+?)\s*$", re.MULTILINE)
_REQ_REF = re.compile(r"\b((?:R|C)-[A-Z]{2,}-\d+)\b")

# --- upstream dialect ------------------------------------------------------
# Heading levels are captured rather than fixed: real repos drift, and the
# drift is worth reporting as drift instead of as "nothing found".
_DELTA_HEADER = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements", re.MULTILINE)
_REQUIREMENT = re.compile(
    r"^(#{2,4})\s+(?:Requirement|REQ\s*\d+)\s*[:\u2014-]\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE
)
_SCENARIO = re.compile(r"^(#{3,5})\s+Scenario\s*[:\u2014-]\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)

# Canonical levels per the upstream OpenSpec convention.
CANONICAL_REQ_LEVEL = 3
CANONICAL_SCEN_LEVEL = 4

_SUPPRESS = re.compile(r"<!--\s*specgraph:allow\s+([A-Z]\d{3}(?:\s*,\s*[A-Z]\d{3})*)\s*(.*?)-->")

# --- shared references -----------------------------------------------------
_MAKE_REF = re.compile(r"`?\bmake\s+([a-z][a-z0-9_-]*)\b`?")
_INV_REF = re.compile(r"\bINV-\d+\b")
_PYTEST_SEL = re.compile(r"pytest\s+-k\s+(\S+)")

# A bare percentage or >= NN in criterion text, which should come from config.
_HARD_THRESHOLD = re.compile(r"(?:≥|>=|>)\s*\d{2,3}\s*%?|\b\d{2,3}\s*%")
_THRESHOLD_ALLOWLIST = (
    "governance-policy.json",
    "pyproject.toml",
    "coverage.lines",
    "coverage.branches",
    "fail_under",
    "policy",
)

# A non-success criterion is one that asserts something is refused, fails, or
# does not happen. Detected by pattern rather than by an exact-phrase list,
# because the phrasings that matter in practice are open-ended -- "opens no
# egress channel" and "mutates neither the remote nor the local tag list" both
# describe failure paths and neither is a fixed idiom.
NEGATIVE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bnon-success\b",
        r"\bnegative\b",
        r"\b(?:must|shall|does|do|is|are|will|would|can|could)\s+not\b",
        r"\bcannot\b",
        r"\bnever\b",
        r"\bneither\b",
        r"\bnothing\b",
        r"\bwithout\b",
        r"\brefus\w*",
        r"\breject\w*",
        r"\bden(?:y|ies|ied|ial)\b",
        r"\bblock(?:s|ed|ing)?\b",
        r"\bfail\w*",
        r"\bmalformed\b",
        r"\binvalid\b",
        r"\bunaffected\b",
        r"\bunchanged\b",
        r"\bcaught\b",
        r"\bnon-?zero\b",
        r"\bzero\b",
        # "opens no egress channel", "no second tag is created"
        r"\bno\s+\w+(?:\s+\w+){0,3}\s+(?:is|are|was|were|opens|occurs|happens|created|written)\b",
        r"\b(?:opens|creates|writes|emits|grants|mutates|leaves)\s+no\b",
    )
)


@dataclasses.dataclass(frozen=True)
class Criterion:
    """A verifiable claim: a harness AC, or an upstream Scenario."""

    ident: str
    text: str
    note: str = ""
    verified_by: str = ""
    requirement_refs: tuple[str, ...] = ()
    line: int = 0

    @property
    def is_negative(self) -> bool:
        blob = f"{self.note} {self.text}"
        return any(p.search(blob) for p in NEGATIVE_PATTERNS)

    @property
    def has_stage(self) -> bool:
        return bool(_MAKE_REF.search(self.verified_by))

    @property
    def has_selector(self) -> bool:
        return bool(_PYTEST_SEL.search(self.verified_by)) or "·" in self.verified_by


@dataclasses.dataclass(frozen=True)
class Requirement:
    ident: str
    text: str
    kind: str  # "functional" | "constraint" | "shall"
    level: int = 0  # markdown heading depth, 0 for list-declared requirements


@dataclasses.dataclass(frozen=True)
class ParsedSpec:
    path: Path
    dialect: str
    sections: tuple[str, ...]
    status: str | None
    requirements: tuple[Requirement, ...]
    criteria: tuple[Criterion, ...]
    make_refs: tuple[str, ...]
    invariant_refs: tuple[str, ...]
    hard_coded_thresholds: tuple[str, ...]
    delta_headers: tuple[str, ...]
    scenario_levels: tuple[int, ...] = ()
    suppressed: frozenset[str] = frozenset()
    raw: str = dataclasses.field(repr=False, default="")

    @property
    def heading_drift(self) -> tuple[str, ...]:
        """Heading depths that deviate from the upstream OpenSpec convention."""
        issues: list[str] = []
        bad_req = sorted({r.level for r in self.requirements if r.level not in (0, CANONICAL_REQ_LEVEL)})
        bad_scen = sorted({lvl for lvl in self.scenario_levels if lvl != CANONICAL_SCEN_LEVEL})
        for lvl in bad_req:
            issues.append(
                f"requirements are at H{lvl} ({'#' * lvl}), convention is "
                f"H{CANONICAL_REQ_LEVEL} (### Requirement:)"
            )
        for lvl in bad_scen:
            issues.append(
                f"scenarios are at H{lvl} ({'#' * lvl}), convention is "
                f"H{CANONICAL_SCEN_LEVEL} (#### Scenario:)"
            )
        return tuple(issues)

    @property
    def has_negative_criterion(self) -> bool:
        return any(c.is_negative for c in self.criteria)

    @property
    def orphan_requirements(self) -> tuple[str, ...]:
        """Requirements no criterion references. Only meaningful for the harness dialect."""
        referenced = {ref for c in self.criteria for ref in c.requirement_refs}
        return tuple(r.ident for r in self.requirements if r.ident not in referenced)


def _section_body(text: str, name: str) -> str:
    bounds = [(m.group(1), m.start(), m.end()) for m in _SECTION.finditer(text)]
    for idx, (title, _start, end) in enumerate(bounds):
        if title.strip().lower() != name.lower():
            continue
        stop = bounds[idx + 1][1] if idx + 1 < len(bounds) else len(text)
        return text[end:stop]
    return ""


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _hard_coded(text: str) -> tuple[str, ...]:
    offenders: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("-") and not line.startswith("|"):
            continue
        if not _HARD_THRESHOLD.search(line):
            continue
        low = line.lower()
        if any(token in low for token in _THRESHOLD_ALLOWLIST):
            continue
        offenders.append(line[:120])
    return tuple(offenders)


def _parse_harness(text: str) -> tuple[tuple[Requirement, ...], tuple[Criterion, ...]]:
    reqs = tuple(
        Requirement(
            ident=m.group(1),
            text=m.group(2),
            kind="constraint" if m.group(1).startswith("C-") else "functional",
        )
        for m in _REQ_DECL.finditer(_section_body(text, "Requirements"))
    )

    ac_body = _section_body(text, "Acceptance Criteria")
    matches = list(_AC.finditer(ac_body))
    criteria: list[Criterion] = []
    for idx, match in enumerate(matches):
        stop = matches[idx + 1].start() if idx + 1 < len(matches) else len(ac_body)
        block = ac_body[match.start() : stop]
        verified = _VERIFIED_BY.search(block)
        criteria.append(
            Criterion(
                ident=match.group(2),
                note=match.group(3).strip(" ()"),
                text=match.group(4),
                verified_by=verified.group(1) if verified else "",
                requirement_refs=tuple(sorted(set(_REQ_REF.findall(block)))),
                line=_line_of(text, text.find(block[:60])) if block else 0,
            )
        )
    return reqs, tuple(criteria)


def _parse_upstream(text: str) -> tuple[tuple[Requirement, ...], tuple[Criterion, ...]]:
    req_matches = list(_REQUIREMENT.finditer(text))
    reqs = tuple(
        Requirement(
            ident=f"REQ-{i + 1}",
            text=m.group(2),
            kind="shall",
            level=len(m.group(1)),
        )
        for i, m in enumerate(req_matches)
    )

    criteria: list[Criterion] = []
    scen_matches = list(_SCENARIO.finditer(text))
    for idx, match in enumerate(scen_matches):
        stop = scen_matches[idx + 1].start() if idx + 1 < len(scen_matches) else len(text)
        block = text[match.start() : stop]
        owning = "REQ-?"
        for i, rm in enumerate(req_matches):
            if rm.start() < match.start():
                owning = f"REQ-{i + 1}"
        criteria.append(
            Criterion(
                ident=f"SCEN-{idx + 1}",
                text=match.group(2),
                note=block,
                verified_by=block,
                requirement_refs=(owning,),
                line=_line_of(text, match.start()),
            )
        )
    return reqs, tuple(criteria)


def _scenario_levels(text: str) -> tuple[int, ...]:
    return tuple(len(m.group(1)) for m in _SCENARIO.finditer(text))


def _suppressions(text: str) -> frozenset[str]:
    found: set[str] = set()
    for match in _SUPPRESS.finditer(text):
        found.update(part.strip() for part in match.group(1).split(","))
    return frozenset(found)


def parse_spec(path: Path, dialect: str) -> ParsedSpec:
    text = path.read_text(encoding="utf-8", errors="replace")
    resolved = dialect
    if resolved in {"mixed", "unknown", "auto"}:
        resolved = (
            "upstream"
            if ("## ADDED Requirements" in text or "#### Scenario:" in text)
            else "harness"
        )

    if resolved in {"mixed", "unknown", "auto"}:
        resolved = "harness"

    if resolved == "upstream":
        reqs, criteria = _parse_upstream(text)
    else:
        reqs, criteria = _parse_harness(text)
        if not reqs and not criteria and _REQUIREMENT.search(text):
            # Written in the upstream form despite the repo-level classification.
            resolved = "upstream"
            reqs, criteria = _parse_upstream(text)

    status = _STATUS.search(text)
    return ParsedSpec(
        path=path,
        dialect=resolved,
        sections=tuple(m.group(1).strip() for m in _SECTION.finditer(text)),
        status=status.group(1).upper() if status else None,
        requirements=reqs,
        criteria=criteria,
        make_refs=tuple(sorted(set(_MAKE_REF.findall(text)))),
        invariant_refs=tuple(sorted(set(_INV_REF.findall(text)))),
        hard_coded_thresholds=_hard_coded(text),
        delta_headers=tuple(m.group(1) for m in _DELTA_HEADER.finditer(text)),
        scenario_levels=_scenario_levels(text),
        suppressed=_suppressions(text),
        raw=text,
    )


def scenario_has_gwt(criterion: Criterion) -> bool:
    blob = criterion.note.upper()
    return all(token in blob for token in ("GIVEN", "WHEN", "THEN"))
