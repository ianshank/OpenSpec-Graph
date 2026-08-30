"""Parser for the upstream OpenSpec dialect (Requirement/Scenario headings)."""

from __future__ import annotations

from .parse_model import Criterion, Requirement
from .parse_semantics import REQUIREMENT, SCENARIO, line_of

__all__ = ["parse_upstream"]


def parse_upstream(text: str) -> tuple[tuple[Requirement, ...], tuple[Criterion, ...]]:
    req_matches = list(REQUIREMENT.finditer(text))
    reqs = tuple(
        Requirement(
            ident=f"REQ-{i + 1}",
            text=m.group(2),
            kind="shall",
            level=len(m.group(1)),
            body=text[m.end() : (req_matches[i + 1].start() if i + 1 < len(req_matches) else len(text))],
        )
        for i, m in enumerate(req_matches)
    )

    criteria: list[Criterion] = []
    scen_matches = list(SCENARIO.finditer(text))
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
                line=line_of(text, match.start()),
            )
        )
    return reqs, tuple(criteria)
