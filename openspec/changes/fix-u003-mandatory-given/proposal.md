# Change: Fix U003 Mandatory GIVEN (UG)

> **Status: proposed.** Found by pointing `planlint --target` at an external
> repository for the first time. Same class as `fix-u004-body-blind-modal-check`
> and `fix-coverage-floor-detection-gap`: a rule that fires on well-formed
> content.

## Why

U003 requires all three of GIVEN, WHEN and THEN to appear in a scenario. In
Gherkin, GIVEN is optional — a scenario whose precondition is folded into its
WHEN is complete and executable. Requiring GIVEN turns correct specs into
blocking errors.

**Evidence:** `openspec_graph/parse.py::scenario_has_gwt` is
`return all(token in blob for token in ("GIVEN", "WHEN", "THEN"))`, and
`rules_upstream.py::_scenario_without_gwt` yields an ERROR for every criterion it
rejects. Run against `ianshank/Agents` — an unrelated repository authoring
OpenSpec deltas in the upstream dialect — `planlint --target <clone> validate
--fail-on ERROR` reports 66 U003 errors across 7 active capability specs and
exits non-zero. Direct measurement of those specs through this repository's own
parser shows 68 scenarios, of which 66 carry both WHEN and THEN and omit only
GIVEN, and **zero** are missing WHEN or THEN. Every reported error is a false
positive; the rule found no real defect.

A representative scenario, from
`openspec/changes/add-panel-judge/specs/panel-judge/spec.md`:

```
#### Scenario: An unknown strategy is rejected at construction

- WHEN a panel is configured with a strategy outside the enumerated set
- THEN construction raises an error naming the supported strategies
```

That is executable as written. There is no precondition to state, and inventing
a GIVEN to satisfy the linter would add nothing a runner could use.

**Why this matters more than the count.** U003 is ERROR severity, so this is not
noise a reader filters — it fails the gate. The stated purpose of this tool is
being safe to point at a repository you do not own, and on its first such run it
would have told a maintainer that 66 correct scenarios were not executable.

## What Changes

- `scenario_has_gwt` requires WHEN and THEN, and treats GIVEN as optional.
- A scenario missing WHEN or THEN keeps failing U003 at ERROR, unchanged.
- The rule summary and README row are reworded so the rule's name stops
  promising a check it no longer makes.
- Fixtures cover the newly-passing shape and the still-failing shapes, derived by
  mutation of the passing fixture.

## Non-Goals

- **No relaxation of U002.** A requirement with no scenario at all is a separate
  rule and stays ERROR.
- **No new rule ID** for "scenario omits GIVEN". A missing optional clause is not
  a finding, and adding a WARN for it would reintroduce the same noise one
  severity down.
- **No change to the harness dialect.** This is upstream-only; the harness
  dialect does not use GIVEN/WHEN/THEN.
- **No waiver as the remedy.** A waiver in the target repository would hide a
  defect in this one.

## Affected Capabilities

- `u003-gwt-shape`
