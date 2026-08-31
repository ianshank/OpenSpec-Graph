"""Parser for the upstream OpenSpec dialect (Requirement/Scenario headings)."""

from __future__ import annotations

from .parse_model import Criterion, Requirement
from .parse_semantics import REQUIREMENT, SCENARIO, line_of, strip_waiver_comments

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
        # A waiver comment's own reason text must never leak a spurious
        # `make X` citation into verified_by -- see parse_harness.py's
        # identical fix for the same bug class. The Scenario block is much
        # wider than harness's single _Verified by:_ line, so a waiver
        # comment anywhere in the block (e.g. right after THEN, a natural
        # place to justify a nearby rule exception) was previously exposed.
        verified_by = strip_waiver_comments(block)
        criteria.append(
            Criterion(
                ident=f"SCEN-{idx + 1}",
                text=match.group(2),
                note=block,
                verified_by=verified_by,
                requirement_refs=(owning,),
                line=line_of(text, match.start()),
            )
        )
    return reqs, tuple(criteria)
