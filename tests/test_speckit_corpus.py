"""Milestone 5: corpus validation for the speckit dialect.

No live network access to pull real `spec-kit`-CLI-generated output in this
environment, so this hand-authors several representative fixtures spanning
the format variance SpecKit's own documented template allows (multiple
prioritized user stories, multi-line Given/When/Then, an in-progress draft
still carrying [NEEDS CLARIFICATION] markers) and runs the full rule set
against each -- the same discipline this repo already applies to
`good_harness.md`/`good_upstream.md`.

Finding from this pass: the original single-line-only `GWT_SCENARIO` missed
a realistic multi-line authoring style; fixed in parse_semantics.py
(see its own comment) rather than left as a known gap. No further
GWT_SCENARIO tightening identified beyond that -- S004 stays at WARN
(R-SK-27) since this remains a hand-authored, not live-collected, corpus.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from openspec_graph import detect, rules
from openspec_graph.parse import parse_spec
from tests.support import write_speckit_spec

GOOD_SPECKIT = Path(__file__).resolve().parent.joinpath("fixtures", "good_speckit.md").read_text(
    encoding="utf-8"
)

# Representative of a spec with multiple prioritized user stories, each with
# its own multi-line acceptance scenario, plus a Success Criteria section --
# a fuller shape than good_speckit.md's single-story minimal case.
MULTI_STORY_SPECKIT = textwrap.dedent(
    """\
    # Feature Specification: Order Checkout

    **Feature Branch**: `002-order-checkout`
    **Status**: Draft

    ## User Scenarios & Testing

    ### User Story 1 - Complete a purchase (Priority: P1)

    A shopper completes checkout and receives a confirmation.

    **Why this priority**: The core transaction the feature exists for.

    **Acceptance Scenarios**:

    1. **Given** a shopper with items in their cart
       **When** they submit payment
       **Then** an order confirmation is shown

    ### User Story 2 - Reject an expired payment method (Priority: P2)

    **Acceptance Scenarios**:

    1. **Given** a shopper whose card has expired, **When** they submit payment, **Then** the payment is declined.

    ## Requirements

    ### Functional Requirements

    - **FR-001**: The system MUST confirm every successful order.
    - **FR-002**: The system MUST decline an expired payment method.

    ## Success Criteria

    - **SC-001**: Checkout completes in under 3 seconds for 99% of orders.
    """
)

# Representative of an in-progress draft: a real, unresolved
# [NEEDS CLARIFICATION] marker left in the document, exactly the situation
# S001 exists to catch.
DRAFT_WITH_OPEN_QUESTION = textwrap.dedent(
    """\
    # Feature Specification: Refund Processing

    **Feature Branch**: `003-refund-processing`
    **Status**: Draft

    ## User Scenarios & Testing

    ### User Story 1 - Issue a refund (Priority: P1)

    1. **Given** a completed order, **When** a refund is requested, **Then** the refund is issued.

    ## Requirements

    ### Functional Requirements

    - **FR-001**: The system MUST issue a refund within [NEEDS CLARIFICATION: what SLA?] of the request.

    ## Success Criteria

    - **SC-001**: Refunds are traceable to their originating order.
    """
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def findings_for(repo: Path, feature: str, body: str) -> list[rules.Finding]:
    path = write_speckit_spec(repo, feature, body)
    prof = detect.profile(repo)
    return rules.evaluate(parse_spec(path, "speckit"), prof)


def rule_ids(findings: list[rules.Finding]) -> set[str]:
    return {f.rule for f in findings}


# --- AC-SK-40: good_speckit.md produces zero unexpected findings end to end


def test_good_speckit_fixture_has_no_unexpected_findings(repo: Path) -> None:
    findings = findings_for(repo, "001-demo-capability", GOOD_SPECKIT)
    assert findings == []


# --- Corpus fixture 1: multiple stories, mixed single-/multi-line GWT ------


def test_multi_story_fixture_has_no_unexpected_findings(repo: Path) -> None:
    findings = findings_for(repo, "002-order-checkout", MULTI_STORY_SPECKIT)
    assert findings == []


# --- Corpus fixture 2: an in-progress draft with a real open question -----


def test_draft_with_open_question_fires_only_s001(repo: Path) -> None:
    ids = rule_ids(findings_for(repo, "003-refund-processing", DRAFT_WITH_OPEN_QUESTION))
    assert ids == {"S001"}
