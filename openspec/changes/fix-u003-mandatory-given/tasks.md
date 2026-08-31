# Milestones

## Milestone 1 — Reproduce against a real target  [DONE]

- Cloned `ianshank/Agents` and ran `planlint --target <clone> validate
  --fail-on ERROR`: 66 U003 errors across 7 active capability specs, exit 1.
- Measured the flagged scenarios through this repository's own parser: 68
  scenarios total, 66 carrying WHEN and THEN while omitting GIVEN, none missing
  WHEN or THEN.
- Confirmed the mechanism in `parse.py::scenario_has_gwt`, which requires all
  three tokens.

- **Gate:** the reproduction is recorded in the spec's Problem Statement with the
  measured counts.

## Milestone 2 — Correct the predicate  [DONE]

- `scenario_has_gwt` requires WHEN and THEN; GIVEN becomes optional.
- Keep the ERROR severity and the message for a scenario genuinely missing WHEN
  or THEN, so the rule's real function is untouched.
- Reword the rule summary in `rules_upstream.py` and the README row so neither
  claims GIVEN is required.

- **Gate:** `make test` green; `make validate` clean against this repository.
- **Landed:** `scenario_has_gwt` now requires WHEN and THEN only, with the
  rationale in its docstring. U003's summary became "scenarios state a
  stimulus and an outcome"; the README row and `tests/baseline_rules.json`
  were updated to match. `tests/test_decomposition.py::_EXPECTED_HASHES` was
  re-pinned for `rules` only -- `validate` and `graph` were byte-identical,
  confirming no finding moved on the fixture corpus and only the advertised
  summary changed.

## Milestone 3 — Fixtures  [DONE]

- Extend the passing upstream fixture with a WHEN/THEN scenario carrying no
  GIVEN, and assert it produces no finding.
- Derive the failing variants from the passing fixture by targeted mutation —
  drop the WHEN, then drop the THEN — and assert each still fails U003 at ERROR.
- Keep a scenario carrying all three clauses in the fixture so the previously
  passing shape stays covered.

- **Gate:** `make test` green; the mutated variants fail and the passing variant
  does not.
- **Landed:** eight tests in `tests/test_graft.py` covering AC-UG-1..8. All
  three negative fixtures are single `.replace()` mutations of
  `GOOD_UPSTREAM`, and `test_u003_negative_fixtures_are_mutations_of_the_positive`
  asserts that provenance so the two cannot drift.

## Milestone 4 — Re-run the external target  [DONE]

- Re-run `planlint --target <clone> validate --fail-on ERROR` against the same
  external clone and record the finding count.
- Any finding that survives is triaged on its merits and filed separately; this
  change is not a licence to silence whatever remains.

- **Gate:** `make pre-pr` green; the external run's remaining findings recorded.
- **Landed:** `ianshank/Agents` went from 66 U003 errors across 7 active
  capability specs, exit 1, to `7 spec(s) checked - 0 error - 0 warn - 0 info`,
  exit 0. No finding survived, and none was silenced by a waiver. The
  harness-dialect target (`Mango_Code_Agent-Harness`) was unaffected, as
  expected: U003 is upstream-only.
