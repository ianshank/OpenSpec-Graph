"""Spec grammar and text-processing helpers, shared across dialect parsers.

Owns the compiled regexes for both dialects (harness + upstream), the
negative-criterion and hard-threshold detectors, heading-drift constants, and
the waiver parser. No dependency on the data model or any dialect parser, so
it sits at the bottom of the parse layer.
"""

from __future__ import annotations

import dataclasses
import re

SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
STATUS = re.compile(r"\*\*Status:\*\*\s*([A-Za-z-]+)")

# --- harness dialect -------------------------------------------------------
AC = re.compile(
    r"^-\s*\[( |x|X)\]\s*\*\*(AC-[A-Z]{2,}-\d+)([^:*]*?):\*\*\s*(.+?)\s*$", re.MULTILINE
)
VERIFIED_BY = re.compile(r"_Verified by:_\s*(.+?)\s*$", re.MULTILINE)
REQ_DECL = re.compile(r"^-\s*((?:R|C)-[A-Z]{2,}-\d+)\s*:\s*(.+?)\s*$", re.MULTILINE)
REQ_REF = re.compile(r"\b((?:R|C)-[A-Z]{2,}-\d+)\b")

# --- upstream dialect ------------------------------------------------------
# Heading levels are captured rather than fixed: real repos drift, and the
# drift is worth reporting as drift instead of as "nothing found".
DELTA_HEADER = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements", re.MULTILINE)
REQUIREMENT = re.compile(
    r"^(#{2,4})\s+(?:Requirement|REQ\s*\d+)\s*[:\u2014-]\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE
)
SCENARIO = re.compile(r"^(#{3,5})\s+Scenario\s*[:\u2014-]\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)

# Canonical levels per the upstream OpenSpec convention.
CANONICAL_REQ_LEVEL = 3
CANONICAL_SCEN_LEVEL = 4

SUPPRESS = re.compile(r"<!--\s*specgraph:allow\s+([A-Z]\d{3}(?:\s*,\s*[A-Z]\d{3})*)\s*(.*?)-->")

# --- shared references -----------------------------------------------------
# Backtick-fencing is required: a bare "make sure"/"make progress" in
# ordinary English prose is not a stage citation. Every real citation in
# this repo's own fixtures already uses backticks (often via the
# `stage:` convention), so this is a precision fix, not a breaking one.
# The \b anchors are redundant once a literal backtick forces the boundary.
MAKE_REF = re.compile(r"`make\s+([a-z][a-z0-9_-]*)`")
INV_REF = re.compile(r"\bINV-\d+\b")
# Bare, no backtick-fencing -- same numeric-suffix shape as INV_REF, and
# "ADR-42" doesn't collide with ordinary prose the way "make progress" does
# (the reason MAKE_REF needed fencing).
ADR_REF = re.compile(r"\bADR-\d+\b")
PYTEST_SEL = re.compile(r"pytest\s+-k\s+(\S+)")

# A bare percentage or >= NN in criterion text, which should come from config.
HARD_THRESHOLD = re.compile(r"(?:≥|>=|>)\s*\d{2,3}\s*%?|\b\d{2,3}\s*%")
THRESHOLD_ALLOWLIST = (
    "governance-policy.json",
    "pyproject.toml",
    ".coveragerc",
    "setup.cfg",
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


def section_body(text: str, name: str) -> str:
    bounds = [(m.group(1), m.start(), m.end()) for m in SECTION.finditer(text)]
    for idx, (title, _start, end) in enumerate(bounds):
        if title.strip().lower() != name.lower():
            continue
        stop = bounds[idx + 1][1] if idx + 1 < len(bounds) else len(text)
        return text[end:stop]
    return ""


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def hard_coded(text: str) -> tuple[str, ...]:
    offenders: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("-") and not line.startswith("|"):
            continue
        if not HARD_THRESHOLD.search(line):
            continue
        low = line.lower()
        if any(token in low for token in THRESHOLD_ALLOWLIST):
            continue
        offenders.append(line[:120])
    return tuple(offenders)


def threshold_values(line: str) -> tuple[int, ...]:
    """Every threshold-shaped number on a line (each HARD_THRESHOLD span), as ints."""
    values: list[int] = []
    for match in HARD_THRESHOLD.finditer(line):
        digits = re.search(r"\d{2,3}", match.group())
        if digits:
            values.append(int(digits.group()))
    return tuple(values)


def scenario_levels(text: str) -> tuple[int, ...]:
    return tuple(len(m.group(1)) for m in SCENARIO.finditer(text))


@dataclasses.dataclass(frozen=True)
class Waiver:
    """One waived rule id from a single `<!-- specgraph:allow RULE[, RULE...]
    reason --> ` comment. A comment naming N rules expands to N Waiver
    records, all sharing that comment's reason and line."""

    rule: str
    reason: str
    line: int


def parse_waivers(text: str) -> tuple[Waiver, ...]:
    found: list[Waiver] = []
    for match in SUPPRESS.finditer(text):
        reason = match.group(2).strip()
        line = line_of(text, match.start())
        for part in match.group(1).split(","):
            found.append(Waiver(rule=part.strip(), reason=reason, line=line))
    return tuple(found)


def suppressions(text: str) -> frozenset[str]:
    """Unchanged signature/behavior; now derived from parse_waivers() so the
    two can never drift apart."""
    return frozenset(w.rule for w in parse_waivers(text))


def strip_waiver_comments(text: str) -> str:
    """Blank out ``<!-- specgraph:allow ... -->`` spans, preserving length
    (and therefore line numbers) so any caller still computing offsets
    against the result stays correct.

    A waiver's own reason text must never be able to satisfy the very
    citation (``INV-n``, ``ADR-n``, a backtick-fenced ``make`` target) it
    exists to waive -- e.g. a comment reading "specgraph:allow G009 ADR-1
    is not yet cited" would otherwise put ``ADR-1`` into ``adr_refs``, silently
    resolving the orphan G009 was waiving instead of waiving it (Copilot
    review finding on PR #13; the identical class of bug already existed,
    unfixed, for ``INV_REF`` since CP-4 -- ``test_g006_is_downgraded_to_info_
    when_waived_anywhere_in_the_tree``'s own test comment names it, worked
    around there by carefully avoiding the pattern in test fixtures rather
    than fixed at the source). Reference-extraction (``MAKE_REF``/
    ``INV_REF``/``ADR_REF``) scans this function's output, never the raw
    text directly, for exactly that reason.
    """
    return SUPPRESS.sub(lambda m: " " * len(m.group()), text)
