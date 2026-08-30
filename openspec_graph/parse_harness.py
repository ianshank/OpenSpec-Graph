"""Parser for the harness dialect spec (lists of R-/C- requirements and ACs)."""

from __future__ import annotations

from .parse_model import Criterion, Requirement
from .parse_semantics import (
    AC,
    REQ_DECL,
    REQ_REF,
    VERIFIED_BY,
    line_of,
    section_body,
)

__all__ = ["parse_harness"]


def parse_harness(text: str) -> tuple[tuple[Requirement, ...], tuple[Criterion, ...]]:
    reqs = tuple(
        Requirement(
            ident=m.group(1),
            text=m.group(2),
            kind="constraint" if m.group(1).startswith("C-") else "functional",
        )
        for m in REQ_DECL.finditer(section_body(text, "Requirements"))
    )

    ac_body = section_body(text, "Acceptance Criteria")
    matches = list(AC.finditer(ac_body))
    criteria: list[Criterion] = []
    for idx, match in enumerate(matches):
        stop = matches[idx + 1].start() if idx + 1 < len(matches) else len(ac_body)
        block = ac_body[match.start() : stop]
        verified = VERIFIED_BY.search(block)
        criteria.append(
            Criterion(
                ident=match.group(2),
                note=match.group(3).strip(" ()"),
                text=match.group(4),
                verified_by=verified.group(1) if verified else "",
                requirement_refs=tuple(sorted(set(REQ_REF.findall(block)))),
                line=line_of(text, text.find(block[:60])) if block else 0,
            )
        )
    return reqs, tuple(criteria)
