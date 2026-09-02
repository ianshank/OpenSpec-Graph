"""Parse an OpenSpec spec document into a dialect-neutral structure.

Both supported dialects reduce to the same shape: a set of normative
requirements, a set of verifiable criteria, and the external references
(make targets, invariant IDs) the document claims.

Decomposed into focused modules; this file is the facade:

- :mod:`parse_semantics` — compiled grammar (both dialects), negative-criterion
  and hard-threshold detectors, heading-drift constants, waiver parser.
- :mod:`parse_model` — ``Criterion``/``Requirement``/``ParsedSpec`` dataclasses.
- :mod:`parse_harness` — harness-dialect parser (R-/C- lists + ACs).
- :mod:`parse_upstream` — upstream-dialect parser (Requirement/Scenario headings).

Public surface (``parse_spec``, ``scenario_has_gwt``, ``ParsedSpec``,
``Criterion``, ``Requirement``, ``Waiver``, and the compiled ``MAKE_REF``) is
re-exported here so existing ``from openspec_graph.parse import ...`` imports
keep working (R-DG-1).
"""

from __future__ import annotations

import logging
from pathlib import Path

from .parse_harness import parse_harness as _parse_harness
from .parse_model import Criterion, ParsedSpec, Requirement
from .parse_semantics import (
    ADR_REF,
    DELTA_HEADER,
    INV_REF,
    MAKE_REF,
    NEGATIVE_PATTERNS,
    SECTION,
    STATUS,
    Waiver,
    hard_coded,
    is_speckit_marked,
    is_upstream_marked,
    parse_waivers,
    scenario_levels,
    strip_waiver_comments,
    threshold_values,
)
from .parse_semantics import REQUIREMENT as _REQUIREMENT
from .parse_speckit import parse_speckit as _parse_speckit
from .parse_upstream import parse_upstream as _parse_upstream

# Backwards-compat alias: graph.py historically read parse._MAKE_REF. Kept so
# any external reader of the pre-split private surface keeps working (R-DG-1).
_MAKE_REF = MAKE_REF

__all__ = [
    "MAKE_REF",
    "NEGATIVE_PATTERNS",
    "Criterion",
    "ParsedSpec",
    "Requirement",
    "SpecReadError",
    "Waiver",
    "parse_spec",
    "parse_waivers",
    "scenario_has_gwt",
    "threshold_values",
]

logger = logging.getLogger("planlint.parse")


class SpecReadError(Exception):
    """A discovered spec path exists but its bytes could not be read.

    Translation of ``OSError`` at the one place specs are read, so every
    caller can distinguish "this repo could not be inspected" (exit 2) from
    "this repo's specs have findings" (exit 1). Letting the raw ``OSError``
    escape produced a traceback and exit 1 -- the code the contract reserves
    for findings -- so a CI job could not tell a broken mount from a failing
    gate. Same defect class as DEC-SD-001 (``init``/``new`` on an unwritable
    target), one verb further in; ``detect.py`` already handled its own reads
    this way (``_threshold``/``_invariants``/``_adrs``).

    Carries the offending ``path`` and the underlying ``reason`` so callers
    render one line without re-deriving either from the message text.

    The exception's own ``str()`` is deliberately terse and *not* the
    operator-facing wording: that lives once, in ``cli._UNREADABLE_SPEC``
    (R-RE-6). A second copy here would be a copy that differs -- this one has
    only the absolute path, which the CLI renders root-relative -- and the
    Agent Skill's exit-code reference quotes the CLI's version verbatim.
    """

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def parse_spec(path: Path, dialect: str) -> ParsedSpec:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # Translated, never swallowed: a spec that cannot be read is a
        # precondition failure, not an absent finding. Silently skipping it
        # would let a permission-denied spec pass a gate that never saw it.
        logger.debug("unreadable spec %s: %s", path, exc.strerror or exc)
        raise SpecReadError(path, exc.strerror or str(exc)) from exc
    resolved = dialect
    if resolved in {"mixed", "unknown", "auto"}:
        if is_upstream_marked(text):
            resolved = "upstream"
        elif is_speckit_marked(text):
            resolved = "speckit"
        else:
            resolved = "harness"

    # Explicit if/elif on the three dialect literals, not a dict/registry --
    # each branch carries its own bespoke escape-hatch logic a dispatch
    # table wouldn't eliminate, and this codebase has an on-the-record
    # precedent against genericizing 2-3-instance special cases (DEC-AD-003,
    # cited by rules.py's evaluate_tree() docstring for the analogous
    # G006/G009 two-block shape).
    if resolved == "upstream":
        reqs, criteria = _parse_upstream(text)
    elif resolved == "speckit":
        reqs, criteria = _parse_speckit(text)
        if not reqs and not criteria and _REQUIREMENT.search(text):
            # Sniffed as speckit but actually written upstream-style.
            resolved = "upstream"
            reqs, criteria = _parse_upstream(text)
    else:
        reqs, criteria = _parse_harness(text)
        if not reqs and not criteria and _REQUIREMENT.search(text):
            # Written in the upstream form despite the repo-level classification.
            resolved = "upstream"
            reqs, criteria = _parse_upstream(text)

    status = STATUS.search(text)
    waivers = parse_waivers(text)
    # A waiver's own reason text must never satisfy the citation it's
    # waiving (e.g. naming "ADR-1" in a G009 waiver's reason must not put
    # ADR-1 into adr_refs and silently resolve the orphan instead of
    # waiving it) -- reference extraction scans the waiver-stripped text,
    # never the raw text directly.
    citation_text = strip_waiver_comments(text)
    return ParsedSpec(
        path=path,
        dialect=resolved,
        sections=tuple(m.group(1).strip() for m in SECTION.finditer(text)),
        status=status.group(1).upper() if status else None,
        requirements=reqs,
        criteria=criteria,
        make_refs=tuple(sorted(set(MAKE_REF.findall(citation_text)))),
        invariant_refs=tuple(sorted(set(INV_REF.findall(citation_text)))),
        hard_coded_thresholds=hard_coded(text, resolved),
        delta_headers=tuple(m.group(1) for m in DELTA_HEADER.finditer(text)),
        scenario_levels=scenario_levels(text),
        suppressed=frozenset(w.rule for w in waivers),
        waivers=waivers,
        raw=text,
        adr_refs=tuple(sorted(set(ADR_REF.findall(citation_text)))),
    )


def scenario_has_gwt(criterion: Criterion) -> bool:
    """Is this scenario executable -- does it name a stimulus and an outcome?

    ``WHEN`` and ``THEN`` are required: a scenario with no stimulus, or with no
    asserted outcome, cannot be run. ``GIVEN`` is **optional** (DEC-UG-001).
    Gherkin treats it as optional, and a scenario whose precondition is folded
    into its ``WHEN`` is complete as written -- requiring it reported 66 of the
    68 scenarios in an external upstream-dialect corpus, none of which was
    actually unexecutable.
    """
    blob = criterion.note.upper()
    return all(token in blob for token in ("WHEN", "THEN"))
