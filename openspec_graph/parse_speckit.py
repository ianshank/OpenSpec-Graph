"""Parser for the SpecKit dialect (prioritized user stories, FR-/SC- bullets).

No delta/ADDED-MODIFIED-REMOVED concept exists in SpecKit's own grammar --
unlike upstream, every spec is a complete, fresh document, never a diff
against a prior one.
"""

from __future__ import annotations

from .parse_model import Criterion, Requirement
from .parse_semantics import (
    FR_DECL,
    GWT_SCENARIO,
    SC_DECL,
    SECTION,
    USER_STORY_HEADING,
    line_of,
    speckit_section_body,
    speckit_subsection_body,
)

__all__ = ["parse_speckit"]


def parse_speckit(text: str) -> tuple[tuple[Requirement, ...], tuple[Criterion, ...]]:
    # "## Requirements *(mandatory)*" (H2, canonical SpecKit template)
    # contains the nested "### Functional Requirements" (H3) subheading +
    # FR bullets. Scanning the whole H2 span would also pick up a bullet
    # shaped like an FR declaration sitting under an unrelated H3 (or with
    # no "### Functional Requirements" heading at all) -- scope to the H3's
    # own span via speckit_subsection_body so only bullets actually declared
    # there count.
    req_section = speckit_section_body(text, "Requirements")
    req_body = speckit_subsection_body(req_section, "Functional Requirements")
    reqs = tuple(
        Requirement(ident=m.group(1), text=m.group(2), kind="functional")
        for m in FR_DECL.finditer(req_body)
    )

    criteria: list[Criterion] = []

    # SC-00N bullets under "## Success Criteria *(mandatory)*" -- SpecKit's
    # closest analogue to harness's ACs. note stays "" (the default): these
    # are measurable outcomes, not Given/When/Then scenarios, so
    # scenario_has_gwt() must not be run against them (S004's own check
    # function guards on `crit.note` being non-empty for exactly this
    # reason -- every SC bullet would otherwise report as "missing
    # WHEN/THEN", which was never a claim it made).
    sc_body = speckit_section_body(text, "Success Criteria")
    for m in SC_DECL.finditer(sc_body):
        criteria.append(
            Criterion(
                ident=m.group(1),
                text=m.group(2),
                requirement_refs=(),
                line=line_of(text, text.find(m.group(0))),
            )
        )

    # Given/When/Then acceptance scenarios are inline numbered prose inside
    # each "### User Story N - ..." block, not a header-per-scenario
    # convention like upstream's "#### Scenario:". Each story's block is
    # bounded by whichever comes first: the next "### User Story" heading,
    # the next H2 section, or end of document -- so a trailing story
    # doesn't accidentally sweep in the unrelated "## Requirements"/
    # "## Success Criteria" sections that structurally follow it.
    story_matches = list(USER_STORY_HEADING.finditer(text))
    section_starts = [m.start() for m in SECTION.finditer(text)]
    for s_idx, story in enumerate(story_matches):
        story_num = story.group(1)
        candidates = [len(text)]
        if s_idx + 1 < len(story_matches):
            candidates.append(story_matches[s_idx + 1].start())
        candidates.extend(pos for pos in section_starts if pos > story.start())
        stop = min(candidates)
        block = text[story.start() : stop]
        for a_idx, scen in enumerate(GWT_SCENARIO.finditer(block)):
            snippet = scen.group(0).strip()
            criteria.append(
                Criterion(
                    ident=f"US{story_num}-AS{a_idx + 1}",
                    text=snippet[:120],
                    note=snippet,
                    requirement_refs=(),
                    line=line_of(text, story.start() + scen.start()),
                )
            )
    return reqs, tuple(criteria)
