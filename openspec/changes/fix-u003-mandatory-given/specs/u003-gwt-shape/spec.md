# Spec: U003 GWT Shape (UG)

> **Change:** `fix-u003-mandatory-given`
> **Version:** 1.0.0
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

U003 rejects any scenario that does not contain all three of GIVEN, WHEN and
THEN. GIVEN is optional in Gherkin: a scenario whose precondition is expressed
inside its WHEN is complete and runnable. Because U003 is ERROR severity, the
rule does not merely annotate such scenarios — it fails the gate on them.

**Evidence:** `openspec_graph/parse.py::scenario_has_gwt` returns
`all(token in blob for token in ("GIVEN", "WHEN", "THEN"))`, and
`rules_upstream.py::_scenario_without_gwt` emits an ERROR for each rejected
criterion. Pointed at a clone of `ianshank/Agents`, a repository authoring
OpenSpec deltas in the upstream dialect, `validate --fail-on ERROR` reported 66
U003 errors over 7 active capability specs and exited non-zero. Parsing those
same specs through this repository's own parser counted 68 scenarios: 66 carried
both WHEN and THEN while omitting GIVEN, and none was missing WHEN or THEN. The
rule produced no true positive on that corpus.

---

## Requirements

- R-UG-1: A scenario carrying WHEN and THEN MUST NOT be reported by U003 when it
  omits GIVEN.
- R-UG-2: A scenario missing WHEN, or missing THEN, MUST continue to fail U003 at
  ERROR severity with its existing message.
- R-UG-3: The rule summary and its published documentation row MUST NOT describe
  GIVEN as required once it is optional.
- R-UG-4: A scenario carrying all three clauses MUST continue to pass, so the
  previously accepted shape is not lost.
- C-UG-1: This change MUST NOT alter U002, which governs a requirement having no
  scenario at all.
- C-UG-2: This change MUST NOT introduce a new rule identifier, or a lower
  severity finding, for a scenario that omits GIVEN.

---

## Acceptance Criteria

- [ ] **AC-UG-1:** An upstream scenario carrying WHEN and THEN and no GIVEN
  produces no U003 finding. (R-UG-1)
  _Verified by:_ `pytest -k test_u003_accepts_a_scenario_without_given` · stage: `make test`

- [ ] **AC-UG-2 (non-success):** An upstream scenario carrying GIVEN and THEN but
  no WHEN still fails U003 at ERROR. (R-UG-2)
  _Verified by:_ `pytest -k test_u003_still_fires_when_when_is_absent` · stage: `make test`

- [ ] **AC-UG-3 (non-success):** An upstream scenario carrying GIVEN and WHEN but
  no THEN still fails U003 at ERROR — a scenario that never states an outcome
  remains unexecutable. (R-UG-2)
  _Verified by:_ `pytest -k test_u003_still_fires_when_then_is_absent` · stage: `make test`

- [ ] **AC-UG-4:** An upstream scenario carrying all three clauses continues to
  produce no finding. (R-UG-4)
  _Verified by:_ `pytest -k test_u003_accepts_a_full_gwt_scenario` · stage: `make test`

- [ ] **AC-UG-5 (non-success):** The failing fixtures are derived from the
  passing fixture by targeted mutation, and a test fails if a failing fixture
  stops differing from its source only by the removed clause. (R-UG-2)
  _Verified by:_ `pytest -k test_u003_negative_fixtures_are_mutations_of_the_positive` · stage: `make test`

- [ ] **AC-UG-6 (non-success):** Neither the rule summary nor the documented rule
  row states that GIVEN is required; a check fails if either reintroduces the
  claim. (R-UG-3)
  _Verified by:_ `pytest -k test_u003_summary_does_not_require_given` · stage: `make test`

- [ ] **AC-UG-7 (non-success):** A requirement carrying no scenario at all still
  fails U002, unchanged by this change. (C-UG-1)
  _Verified by:_ `pytest -k test_u002_unchanged_by_the_u003_fix` · stage: `make test`

- [ ] **AC-UG-8 (non-success):** No rule identifier is added and no finding of
  any severity is emitted for an omitted GIVEN; the registry baseline is
  unchanged in count and identifiers. (C-UG-2)
  _Verified by:_ `pytest -k test_rule_registry_baseline_is_unchanged` · stage: `make validate`

---

## Decisions

- **DEC-UG-001 (resolved):** GIVEN becomes optional rather than being reported at
  a lower severity. A WARN for an omitted optional clause reproduces the same
  false-positive volume one severity down, and the measured corpus contained no
  case where the omission indicated a defect.
- **DEC-UG-002 (resolved):** WHEN and THEN both stay mandatory. A scenario with
  no stimulus, or with no asserted outcome, genuinely cannot be executed, which
  is the property U003 exists to check.
- **DEC-UG-003 (resolved):** The fix lands in the predicate, not in the rule
  body. `scenario_has_gwt` is the shared, exported surface, so correcting it
  keeps the rule and any future consumer consistent.
- **DEC-UG-004 (resolved):** The external corpus is re-run after the fix rather
  than assumed clean. A change justified by a measurement is verified by the same
  measurement.

---

## Non-Success Criteria (what this change rejects)

- Treating an omitted GIVEN as a finding at any severity is rejected
  (AC-UG-8, DEC-UG-001).
- Relaxing the WHEN or THEN requirement is rejected; that would remove the
  rule's only true function (AC-UG-2, AC-UG-3, DEC-UG-002).
- Waiving U003 in the target repository as the remedy is rejected: it would
  conceal a defect in this repository behind an annotation in someone else's.
- Hand-authoring the failing fixtures independently of the passing one is
  rejected, because the two would drift (AC-UG-5).
- Declaring this change complete without re-running the external corpus is
  rejected (DEC-UG-004).

---

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Unit | `make test` | AC-UG-1 through AC-UG-7 |
| Focused | `make validate` | AC-UG-8; this package validates clean against the repository's own rules |
| Full | `make ci` | No regression in the existing suite, lint, type-check, or the decomposition-guard hash pins |
| Pre-submission | `make pre-pr` | All of the above green; external corpus re-run recorded |
