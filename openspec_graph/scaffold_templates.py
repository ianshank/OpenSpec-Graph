"""Document templates for generated change packages.

Pure functions only — no filesystem access, no profile dependency. Kept separate
from ``scaffold.py`` so document wording and write semantics change
independently. ``scaffold.py`` imports these and decides what to write where.
"""

from __future__ import annotations


def proposal(name: str, capability: str) -> str:
    return f"""# Change: {name.replace("-", " ").title()}

## Why

<!-- What is wrong or missing. Attach evidence: a failing test, a governance
     gap, a user report. No evidence, no spec. -->

## What Changes

- <!-- one bullet per externally visible change -->

## Non-Goals

- <!-- name what this change explicitly does not do, so scope cannot drift -->
- No claim of isolation or sandboxing unless a mechanism is cited.

## Affected Capabilities

- `{capability}`
"""


def tasks(name: str, stage: str, full: str) -> str:
    return f"""# Milestones

## Milestone 1 — <name>

- <!-- ordered work; each step declares what it reads and what it leaves behind -->
- **Gate:** `make {stage}` green; every acceptance criterion for this milestone passes.

## Milestone 2 — Evidence and release

- Wire new gates into the repo's required-target list.
- Confirm coverage floors from the repo threshold source.
- **Gate:** `make {full}` green on the full matrix; zero unapproved test skips.
"""


def spec_harness(capability: str, change: str, stage: str, full: str, locator: str) -> str:
    title = capability.replace("-", " ").title()
    area = "".join(w[0] for w in capability.split("-"))[:3].upper() or "CAP"
    return f"""# Spec: {title}

> **Change:** `{change}`
> **Version:** 1.0.0-draft
> **Authors:** <role> · <role>
> **Status:** DRAFT

---

## Problem Statement

<!-- What is broken or unverifiable today. Cite the file and symbol that proves
     it. **Evidence:** `path/to/module.py::symbol` does X but not Y. -->

---

## Requirements

- R-{area}-1: The system MUST <observable behavior>, sourced from configuration
  rather than a literal value.
- C-{area}-1: The change MUST NOT weaken any declared invariant.

## Acceptance Criteria

- [ ] **AC-{area}-1:** <observable, executable check>. (R-{area}-1)
  _Verified by:_ `pytest -k test_<selector>` · stage: `make {stage}`

- [ ] **AC-{area}-2 (non-success):** <what this rejects, denies, or fails closed
  on; name the expected failure message>. (C-{area}-1)
  _Verified by:_ `pytest -k test_<negative_selector>` · stage: `make {stage}`

- [ ] **AC-{area}-3:** Coverage meets the floor declared in `{locator}`. No
  literal threshold appears in this document or its tests.
  _Verified by:_ `make {full}`

## Invariants Touched

- <!-- INV-n: how it is preserved, and which AC proves it -->

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused gate | `make {stage}` | AC-{area}-1..2 pass |
| Full pipeline | `make {full}` | all of the above |

## Backward Compatibility

<!-- The deprecation or compatibility path for existing callers. -->

## Open Questions

> [!IMPORTANT]
> **DEC-{area}-001 (BLOCKING):** <question that must be resolved before the
> first milestone gate>.
"""


def spec_upstream(capability: str, stage: str) -> str:
    title = capability.replace("-", " ").capitalize()
    return f"""# Spec delta — {title}

## ADDED Requirements

### Requirement: <the system> SHALL <normative, observable behavior>

<!-- Prose stating the obligation precisely. Use SHALL or MUST. -->

#### Scenario: the gate enforces the requirement

- **GIVEN** <the starting state>
- **WHEN** `make {stage}` runs <the named check>
- **THEN** <the observable pass condition>

#### Scenario: a future regression is caught before merge

- **GIVEN** a hypothetical edit that violates the requirement
- **WHEN** the suite runs
- **THEN** the check fails and names the offending file
"""
