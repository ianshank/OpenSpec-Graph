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
``Criterion``, ``Requirement``, and the compiled ``MAKE_REF``) is re-exported
here so existing ``from openspec_graph.parse import ...`` imports keep working
(R-DG-1).
"""

from __future__ import annotations

from pathlib import Path

from .parse_harness import parse_harness as _parse_harness
from .parse_model import Criterion, ParsedSpec, Requirement
from .parse_semantics import (
    DELTA_HEADER,
    INV_REF,
    MAKE_REF,
    NEGATIVE_PATTERNS,
    SECTION,
    STATUS,
    hard_coded,
    scenario_levels,
    suppressions,
    threshold_values,
)
from .parse_semantics import REQUIREMENT as _REQUIREMENT
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
    "parse_spec",
    "scenario_has_gwt",
    "threshold_values",
]


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

    status = STATUS.search(text)
    return ParsedSpec(
        path=path,
        dialect=resolved,
        sections=tuple(m.group(1).strip() for m in SECTION.finditer(text)),
        status=status.group(1).upper() if status else None,
        requirements=reqs,
        criteria=criteria,
        make_refs=tuple(sorted(set(MAKE_REF.findall(text)))),
        invariant_refs=tuple(sorted(set(INV_REF.findall(text)))),
        hard_coded_thresholds=hard_coded(text),
        delta_headers=tuple(m.group(1) for m in DELTA_HEADER.finditer(text)),
        scenario_levels=scenario_levels(text),
        suppressed=suppressions(text),
        raw=text,
    )


def scenario_has_gwt(criterion: Criterion) -> bool:
    blob = criterion.note.upper()
    return all(token in blob for token in ("GIVEN", "WHEN", "THEN"))
