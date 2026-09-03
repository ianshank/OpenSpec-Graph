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
SUBSECTION = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
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

# --- speckit dialect ---------------------------------------------------------
FR_ID = re.compile(r"\bFR-\d+\b")
SC_ID = re.compile(r"\bSC-\d+\b")

# `- **FR-001**: text` / `- **SC-001**: text` -- anchored so a sibling bullet
# like `- **NFR-001**: text` (a plausible "Non-Functional Requirements"
# subsection) cannot match: `\*\*(FR-\d+)` requires the literal `F`
# immediately after the opening `**`, not after an `N`.
FR_DECL = re.compile(r"^-\s*\*\*(FR-\d+)\*\*\s*:\s*(.+?)\s*$", re.MULTILINE)
SC_DECL = re.compile(r"^-\s*\*\*(SC-\d+)\*\*\s*:\s*(.+?)\s*$", re.MULTILINE)
# The bare (unannotated) heading name speckit_section_body() looks up --
# shared by parse_speckit.py's own Success Criteria lookup and this module's
# hard_coded() exemption below, so the two can't independently drift.
SPECKIT_SUCCESS_CRITERIA_HEADING = "Success Criteria"
NEEDS_CLARIFICATION = re.compile(r"\[NEEDS CLARIFICATION(?:\s*:\s*(.*?))?\]", re.IGNORECASE)
USER_STORY_HEADING = re.compile(r"^###\s+User Story\s+(\d+)\b.*$", re.MULTILINE | re.IGNORECASE)
# "1. **Given** ..., **When** ..., **Then** ..." -- SpecKit's own documented
# inline-prose acceptance-scenario convention, distinct from upstream's
# heading-per-scenario "#### Scenario:" form. A prose-scrape, not a rigid
# heading match -- provisional until validated against real SpecKit output
# (Milestone 5); any rule depending on it stays at WARN until then.
#
# Milestone 5 finding: a purely single-line version of this pattern missed a
# realistic, equally-plausible SpecKit authoring style -- Given/When/Then
# each on their own line within the same numbered item, e.g.:
#     1. **Given** an attested writer
#        **When** a write occurs
#        **Then** an evidence id is recorded
# DOTALL lets the inner spans cross newlines to catch that form too; the
# trailing lookahead (rather than `\s*$`) stops the match at the next
# numbered item, a blank line, or end of text, instead of running on into
# unrelated later content once `.` matches `\n` -- verified against two
# sequential multi-line scenarios and a scenario immediately followed by an
# unrelated "## Requirements" section, neither bleeds into the other.
#
# Post-review hardening: originally required the literal Given/When/Then
# keywords in the match itself, which meant a malformed scenario missing
# WHEN or THEN was never captured as a Criterion at all -- S004 (which
# exists to flag exactly that) could never fire against real parsed output,
# only against a hand-built ParsedSpec in a unit test. Matches any numbered
# item in a User Story block now, GWT-complete or not, using the same
# boundary lookahead as before; completeness is decided downstream by
# scenario_has_gwt() (already the source of truth S004 itself calls), not
# by this regex, so a genuinely incomplete scenario is now captured and can
# be reported instead of silently disappearing.
GWT_SCENARIO = re.compile(
    r"^\d+\.\s*.+?(?=\n\s*\d+\.|\n\s*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)

# --- dialect classification (shared between detect.py and parse.py) --------
# Single source of truth for "does this text look like dialect X". Previously
# duplicated independently in detect.py's detect_dialect() and parse.py's
# parse_spec() pre-resolution branch; unified here so the two can never
# silently drift apart, rather than adding a third, naively-duplicated copy
# for speckit.
AC_ID = re.compile(r"\bAC-[A-Z]{2,}-\d+\b")


def is_upstream_marked(text: str) -> bool:
    return "## ADDED Requirements" in text or "#### Scenario:" in text


def is_harness_marked(text: str) -> bool:
    return "## Acceptance Criteria" in text and bool(AC_ID.search(text))


def is_speckit_marked(text: str) -> bool:
    return ("### Functional Requirements" in text and bool(FR_ID.search(text))) or (
        "## Success Criteria" in text and bool(SC_ID.search(text))
    )


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
# The number may carry a decimal fraction: coverage.py accepts a fractional
# floor, `detect` now reports one faithfully, and G003's "cites the exact
# detected floor" suppression has to be able to see 85.5 as 85.5 rather than
# as 85 -- otherwise the one repo whose floor is fractional gets a false G003
# on every criterion that cites it correctly.
HARD_THRESHOLD = re.compile(r"(?:≥|>=|>)\s*\d{2,3}(?:\.\d+)?\s*%?|\b\d{2,3}(?:\.\d+)?\s*%")
_THRESHOLD_NUMBER = re.compile(r"\d{2,3}(?:\.\d+)?")
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

# --- non-success detection (G002) ------------------------------------------
#
# A non-success criterion is one that asserts something is refused, fails, or
# does not happen. Detected by pattern rather than by an exact-phrase list,
# because the phrasings that matter in practice are open-ended -- "opens no
# egress channel" and "mutates neither the remote nor the local tag list" both
# describe failure paths and neither is a fixed idiom.
#
# The patterns are tiered, and the tier is the design rather than a label. An
# earlier flat list of bare lexical triggers (`zero`, `block`, `fail`,
# `without`) scored precision 0.38 / recall 0.42 against a hand-labelled set of
# 86 criterion sentences -- worse than useless for a rule whose failure mode is
# *silence*: G002 asks only whether a spec has at least ONE non-success
# criterion, so a single false positive anywhere in the document switches the
# rule off. "The block renders below the header" used to satisfy it. Measured
# again after this tiering and a second adversarial round: precision 0.92,
# recall 0.98.
#
#   annotation -- the author said so. Harness-dialect criteria carry a
#                 parenthesised marker ("**AC-WM-3 (non-success):**"), which is
#                 an explicit declaration, not prose to be interpreted. Matched
#                 against the annotation ONLY, so a criterion merely discussing
#                 negative numbers is not promoted by the word.
#   structural -- grammar that means absence or refusal wherever it appears
#                 ("cannot", "no X is created", "writes no", "exits 2"). Every
#                 pattern in this tier scored zero false positives.
#   lexical    -- a word whose *verb* forms mean failure but whose noun forms
#                 are ordinary software vocabulary. Each is restricted to the
#                 inflections that are actually verbal, and refuses a following
#                 hyphen, which is what separates "the write is denied" from
#                 "denied-list entries", "the run fails" from "--cov-fail-under",
#                 and "the request is blocked" from "blocking I/O".
#
# `tools/matcher_accuracy.py` scores this table against
# `tests/fixtures/phrasing/`; `tests/test_matcher_accuracy.py` holds it to the
# floors declared in `pyproject.toml`. Adding a pattern here without moving
# those numbers is the point: the table is data, and its accuracy is a tracked
# figure rather than a claim.

ANNOTATION_TIER = "annotation"
STRUCTURAL_TIER = "structural"
LEXICAL_TIER = "lexical"


@dataclasses.dataclass(frozen=True)
class NegationPattern:
    """One named, tiered non-success detector."""

    name: str
    tier: str
    pattern: re.Pattern[str]


def _negation(name: str, tier: str, source: str) -> NegationPattern:
    # IGNORECASE on every pattern without exception: G002 must not turn on how
    # a criterion happens to be capitalised, an invariant
    # tests/test_properties.py holds by construction.
    return NegationPattern(name, tier, re.compile(source, re.IGNORECASE))


NEGATION_PATTERNS: tuple[NegationPattern, ...] = (
    # -- annotation: matched against the criterion's own marker only ---------
    _negation("annotated_non_success", ANNOTATION_TIER, r"\b(?:non-success|negative)\b"),
    # -- structural ---------------------------------------------------------
    _negation("non_success", STRUCTURAL_TIER, r"\bnon-success\b"),
    # A prohibition is always an obligation about a failure path.
    _negation("prohibition", STRUCTURAL_TIER, r"\b(?:must|shall|should|may)\s+not\b"),
    # A negated verb usually states an outcome ("is not created", "does not
    # retry") but sometimes a capability ("does not require a Makefile", "is
    # not nullable"); the latter are counted honestly against this pattern in
    # the corpus. "IS NOT NULL" is a SQL predicate being described.
    _negation(
        "negated_verb",
        STRUCTURAL_TIER,
        r"\b(?:does|do|is|are|was|were|will|would|can|could)\s+not\b(?!\s+null\b)",
    ),
    _negation("cannot", STRUCTURAL_TIER, r"\bcannot\b"),
    # (?!-): "never-expiring tokens" is a feature, not an absence.
    _negation("never", STRUCTURAL_TIER, r"\bnever\b(?!-)"),
    _negation("neither", STRUCTURAL_TIER, r"\bneither\b"),
    # "no second tag is created"
    _negation(
        "no_subject_verb",
        STRUCTURAL_TIER,
        r"\bno\s+\w+(?:\s+\w+){0,3}\s+(?:is|are|was|were|opens|occurs|happens|created"
        r"|written|recorded|emitted|appears)\b",
    ),
    # "opens no egress channel"
    _negation(
        "verb_no",
        STRUCTURAL_TIER,
        r"\b(?:opens|creates|writes|emits|grants|mutates|leaves|records|returns"
        r"|produces|adds|sends|makes)\s+no\b",
    ),
    _negation(
        "nothing",
        STRUCTURAL_TIER,
        r"\b(?:opens|creates|writes|emits|grants|mutates|leaves|records|returns"
        r"|produces|does|changes|reports)\s+nothing\b|\bnothing\s+(?:is|are|was|were)\b",
    ),
    # Anchored to an exit/status context: "every non-zero balance" is a report
    # about data, not a failing run.
    _negation(
        "non_zero_exit",
        STRUCTURAL_TIER,
        r"\bnon-?zero\s+(?:exit|status|code|return)\w*\b"
        r"|\b(?:exits?|exited|returns?|status|code)\s+(?:with\s+)?(?:an?\s+)?non-?zero\b",
    ),
    _negation(
        "exit_code",
        STRUCTURAL_TIER,
        # `status` as well as `code`; and a trailing time unit means "exits 10
        # seconds after SIGTERM" -- a duration, not an exit code.
        r"\bexits?\s+(?:with\s+)?(?:(?:code|status)\s+)?[1-9]\d*\b"
        r"(?!\s*(?:s|sec|secs|seconds?|ms|min|minutes?|hours?)\b)"
        r"|\bexit\s+(?:(?:code|status)\s+)?[1-9]\d*\b",
    ),
    _negation(
        "http_error",
        STRUCTURAL_TIER,
        # `gets` is excluded: "gets 500 requests per second" is throughput.
        r"\b(?:returns?|yields?|responds?(?:\s+with)?|receives?|answers?\s+with"
        r"|bounced\s+with|results?\s+in)\s+(?:an?\s+)?(?:HTTP\s+)?[45]\d{2}\b"
        r"|\bgets?\s+an?\s+(?:HTTP\s+)?[45]\d{2}\b"
        r"|\b(?:HTTP\s+)?[45]\d{2}\s+(?:is|are|was|were)\s+returned\b",
    ),
    _negation("no_op", STRUCTURAL_TIER, r"\bno-?ops?\b"),
    # Predicative only: "is unchanged", "leaves the tree untouched". The
    # attributive form ("skips unchanged files") describes input, not outcome.
    _negation(
        "state_preserved",
        STRUCTURAL_TIER,
        r"\b(?:is|are|was|were|remains?|remained|stays?|stayed|left)\s+"
        r"(?:unchanged|untouched|unmodified|unaffected)\b(?!-)"
        r"|\b(?:leaves?|left|keeps?|kept)\s+\w+(?:\s+\w+){0,3}\s+"
        r"(?:unchanged|untouched|unmodified|unaffected)\b(?!-)",
    ),
    _negation(
        "remains_absent",
        STRUCTURAL_TIER,
        r"\b(?:remains?|stays?|stayed|remained)\s+(?:absent|empty|off|unset|closed"
        r"|disabled|untouched)\b",
    ),
    # The bare word "negative" belongs to the annotation tier; in prose it needs
    # a noun to mean a failure path rather than a number below zero.
    _negation(
        "negative_case",
        STRUCTURAL_TIER,
        r"\bnegative\s+(?:case|cases|path|paths|test|tests|scenario|scenarios"
        r"|criterion|criteria|outcome|outcomes)\b",
    ),
    # -- lexical ------------------------------------------------------------
    # Each excludes its own nominalisation ("refusal", "rejection", "denial")
    # and, via (?!-), its hyphenated attributive use.
    _negation("refuse", LEXICAL_TIER, r"\brefus(?:e|es|ed|ing)\b"),
    _negation("reject", LEXICAL_TIER, r"\breject(?:s|ed|ing)?\b(?!-)"),
    _negation("deny", LEXICAL_TIER, r"\bden(?:y|ies|ied)\b(?!-)"),
    _negation("fail", LEXICAL_TIER, r"\bfail(?:s|ed|ing)?\b(?!-)"),
    # The noun only in an outcome position: "on failure", "the failure is
    # reported" -- not "the word failure appears in the glossary".
    _negation(
        "failure",
        LEXICAL_TIER,
        r"\b(?:on|upon|after)\s+(?:\w+\s+){0,2}failure\b|\bfailures?\s+(?:is|are|was|were)\b"
        r"|\bfailure\s+(?:mode|path|case)s?\b",
    ),
    # Copula-anchored: "block" is overwhelmingly a noun in software prose.
    _negation(
        "blocked", LEXICAL_TIER, r"\b(?:is|are|was|were|be|been|being|gets?|got)\s+blocked\b"
    ),
    _negation("abort", LEXICAL_TIER, r"\babort(?:s|ed|ing)?\b"),
    _negation("halt", LEXICAL_TIER, r"\bhalt(?:s|ed|ing)?\b"),
    _negation("decline", LEXICAL_TIER, r"\bdeclin(?:e|es|ed|ing)\b"),
    # Passive only, as one pattern: the active forms are ordinary software
    # verbs ("the user can skip the tutorial", "users may drop tables",
    # "the importer ignores whitespace", "kill switch") and scored worse than
    # chance in review. "The job is skipped" / "changes are dropped" are the
    # outcome uses that survive.
    _negation(
        "passive_refusal",
        LEXICAL_TIER,
        r"\b(?:is|are|was|were|be|been|being|gets?|got)\s+"
        r"(?:skipped|dropped|ignored|killed|terminated)\b",
    ),
    _negation("prevent", LEXICAL_TIER, r"\bprevent(?:s|ed|ing)?\b"),
    # No bare "timeout(s)": "timeouts are configurable" is a setting.
    _negation("timeout", LEXICAL_TIER, r"\btimes?\s+out\b|\btimed[\s-]out\b"),
    # Only raising an error/exception: "raises the coverage floor" is success.
    _negation(
        "raise", LEXICAL_TIER, r"\brais(?:e|es|ed|ing)\s+(?:an?\s+)?\w*(?:error|exception)s?\b"
    ),
    _negation("error_out", LEXICAL_TIER, r"\berrors?\s+out\b"),
    _negation(
        "error_result",
        LEXICAL_TIER,
        r"\b(?:raises?|returns?|reports?|emits?|shows?|displays?|yields?|produces?"
        r"|receives?|gets?|sees?|is|are)\s+(?:an?\s+)?(?:\w+\s+)?errors?\b",
    ),
    _negation("invalid", LEXICAL_TIER, r"\binvalid\b(?!-)"),
    _negation("malformed", LEXICAL_TIER, r"\bmalformed\b(?!-)"),
    # "caught up with upstream" is progress, not an exception being handled.
    _negation("caught", LEXICAL_TIER, r"\bcaught\b(?!\s+up\b)"),
    _negation(
        "rollback", LEXICAL_TIER, r"\b(?:rolls?\s+back|rolled\s+back|revert(?:s|ed|ing)?)\b"
    ),
)


def negation_matches(note: str, text: str) -> tuple[str, ...]:
    """Names of every negation pattern matching this criterion, in table order.

    ``note`` is the criterion's own parenthesised annotation and ``text`` its
    prose. Annotation-tier patterns see only ``note`` -- that separation is the
    whole point of the tier, since "negative" as a declared marker and
    "negative" in a sentence about numbers are different claims.

    Returns names rather than a bare bool so a caller can report *why* a
    criterion counted, which is what makes a G002 finding arguable instead of
    mysterious. :attr:`parse_model.Criterion.is_negative` is the boolean view.
    """
    blob = f"{note} {text}"
    return tuple(
        p.name
        for p in NEGATION_PATTERNS
        if p.pattern.search(note if p.tier == ANNOTATION_TIER else blob)
    )


# --- normative language (U004 / S003) --------------------------------------
#
# Word-bounded, deliberately. This was a bare case-insensitive *substring* test
# for "SHALL"/"MUST", which made "shallow clone", "Marshalling", "mustard" and
# an env var named MUST_ROTATE_KEYS all read as normative -- and because U004
# fires when a requirement is NOT normative, every one of those silently
# switched the rule off for that requirement. Scored 0.47 precision on a
# hand-labelled set of 32 requirement texts; the boundaries remove that class
# of false pass outright.
#
# Scope unchanged: this asks "does the requirement use SHALL/MUST", which is
# exactly what U004's message claims. Broader modals ("should", "is required
# to", bare imperatives) are a separate question about what *counts* as
# normative, and answering it belongs in a change package of its own rather
# than smuggled into a boundary fix.
# (?!-) additionally rejects the hyphenated noun compound -- "the must-have
# list", "a shall-not-pass rule" -- where the word is a modifier rather than a
# modal. Known and accepted limitation: an interrogative ("Shall we keep the
# legacy endpoint?") still reads as normative. It is a question rather than an
# obligation, but distinguishing the two needs more than a lexical test, and
# it is counted honestly against U004's measured precision rather than
# special-cased away.
NORMATIVE_MODAL = re.compile(r"\b(?:SHALL|MUST)\b(?!-)", re.IGNORECASE)


# Backwards-compatible view for callers that only ever wanted the compiled
# prose patterns (it is re-exported through parse.py's __all__). Annotation-tier
# patterns are deliberately excluded: applied to free text they would reproduce
# the bare-word false positives the tiering exists to remove. Prefer
# negation_matches(), which applies each tier to the field it is written for.
NEGATIVE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    p.pattern for p in NEGATION_PATTERNS if p.tier != ANNOTATION_TIER
)


def section_body(text: str, name: str) -> str:
    bounds = [(m.group(1), m.start(), m.end()) for m in SECTION.finditer(text)]
    for idx, (title, _start, end) in enumerate(bounds):
        if title.strip().lower() != name.lower():
            continue
        stop = bounds[idx + 1][1] if idx + 1 < len(bounds) else len(text)
        return text[end:stop]
    return ""


# Strips a trailing markdown-emphasized parenthetical off a heading title,
# e.g. "*(mandatory)*", "*(include if feature involves data)*".
_TRAILING_ANNOTATION = re.compile(r"[\s*_]*\(.*?\)[\s*_]*$")


def speckit_section_body(text: str, name: str) -> str:
    """Like :func:`section_body`, but tolerates a trailing annotation on the
    heading.

    The canonical SpecKit template suffixes its mandatory H2 headings --
    ``## Requirements *(mandatory)*``, ``## Success Criteria *(mandatory)*``
    -- so :func:`section_body`'s exact-title match silently finds nothing
    against real SpecKit output (confirmed directly against the live
    ``github/spec-kit`` template, not assumed): every FR-/SC- bullet a real,
    correctly-formatted spec declares would go unextracted, and G003's
    Success-Criteria exemption (R-SK-19) would never find its span to
    blank, defeating the fix it exists to apply. Strips a trailing
    parenthetical (optionally wrapped in markdown emphasis) before
    comparing, rather than a loose prefix match, so "Success Criteria"
    still doesn't spuriously match an unrelated "Success Metrics" heading.
    A separate function, not a change to :func:`section_body` itself --
    that function is shared with harness/upstream, whose headings carry no
    such annotations today, and this repo has an explicit
    zero-behavior-change commitment for both (C-SK-8).
    """
    bounds = [(m.group(1), m.start(), m.end()) for m in SECTION.finditer(text)]
    name_lower = name.lower()
    for idx, (title, _start, end) in enumerate(bounds):
        normalized = _TRAILING_ANNOTATION.sub("", title.strip()).strip().lower()
        if normalized != name_lower:
            continue
        stop = bounds[idx + 1][1] if idx + 1 < len(bounds) else len(text)
        return text[end:stop]
    return ""


def speckit_subsection_body(section_text: str, name: str) -> str:
    """Like :func:`speckit_section_body`, one heading level down (H3 inside
    an already-isolated H2 span).

    ``section_body(text, "Requirements")`` returns the *entire* H2 span,
    including any unrelated H3 subsections that happen to sit alongside
    "### Functional Requirements" -- a bullet shaped like ``- **FR-099**:
    ...`` under a different H3 (or with no "### Functional Requirements"
    heading at all) would otherwise be picked up as a real requirement.
    Scoping to the named H3's own span, the same bounded-by-next-heading
    technique :func:`section_body`/:func:`speckit_section_body` already use
    at H2, closes that gap: a wrong-heading or missing-heading document
    yields an empty span, not a false match.
    """
    bounds = [(m.group(1), m.start(), m.end()) for m in SUBSECTION.finditer(section_text)]
    name_lower = name.lower()
    for idx, (title, _start, end) in enumerate(bounds):
        if title.strip().lower() != name_lower:
            continue
        stop = bounds[idx + 1][1] if idx + 1 < len(bounds) else len(section_text)
        return section_text[end:stop]
    return ""


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def hard_coded(text: str, dialect: str = "") -> tuple[str, ...]:
    """Every hard-coded-threshold offender line, dialect-neutral by default.

    ``dialect == "speckit"`` exempts the ``Success Criteria`` section body
    from the scan (R-SK-19, mandatory fix): a conventional, purely
    positive-phrased SpecKit Success Criterion like ``SC-001: 95% of new
    users complete onboarding in under 5 minutes`` is a completely
    legitimate bare-percentage bullet, not a hard-coded value that should
    instead come from the repo's coverage/governance config -- the
    intent this check exists to enforce for harness/upstream. Uses
    :func:`speckit_section_body`, not :func:`section_body`, to find the
    span -- the canonical SpecKit template's heading is
    ``## Success Criteria *(mandatory)*``, and an exact-title lookup would
    silently find nothing against it, defeating this exemption entirely
    against real SpecKit output. Blanks the section span rather than
    skipping it structurally, preserving length (and therefore line
    numbers), the same technique ``strip_waiver_comments()`` uses for the
    identical reason. Zero behavior change for harness/upstream: neither
    existing fixture has a ``Success Criteria`` heading, and the default
    ``dialect=""`` never triggers this branch.
    """
    scan_text = text
    if dialect == "speckit":
        span = speckit_section_body(text, SPECKIT_SUCCESS_CRITERIA_HEADING)
        if span:
            start = text.index(span)
            scan_text = text[:start] + " " * len(span) + text[start + len(span) :]
    offenders: list[str] = []
    for raw_line in scan_text.splitlines():
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


def threshold_values(line: str) -> tuple[int | float, ...]:
    """Every threshold-shaped number on a line (each HARD_THRESHOLD span).

    An integral value comes back as ``int`` and a fractional one as ``float``,
    the same contract as ``detect.as_threshold_number`` -- so ``values[0] ==
    profile.threshold.value`` compares like with like whichever way the floor
    was written.
    """
    values: list[int | float] = []
    for match in HARD_THRESHOLD.finditer(line):
        number = _THRESHOLD_NUMBER.search(match.group())
        if number:
            value = float(number.group())
            values.append(int(value) if value.is_integer() else value)
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
