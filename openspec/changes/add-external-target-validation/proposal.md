# Change: Add External-Target Validation (XTV)

> **Status: proposed.** No legal precondition. This package is startable
> immediately and deliberately contains no reference to any repository under
> legal hold.

## Why

`planlint` advertises itself as *"the tool you point at someone else's
repository"* (`docs/differentiation-roadmap.md`), and the mechanism exists:
`cli.py` declares `parser.add_argument("--target", default=".", help="path to
the cloned repository")` on the top-level parser, resolved by `_profile()` for
every verb. But the corpus it has been proven against is narrow, and one shape
it will certainly meet in the field is absent from it entirely.

**Evidence:** every change package in this repository is exactly three files —
`scaffold.plan_change()` emits `proposal.md`, `tasks.md`, and
`specs/<capability>/spec.md`, and `test_apply_is_idempotent_and_refuses_to_clobber`
asserts `len(first) == 3`. `ianshank/Agents`, a repository that also authors
OpenSpec change packages, uses a five-file shape: its `openspec/README.md`
documents `proposal.md`, `design.md`, `tasks.md`, `review.md`, and
`specs/<capability>/spec.md`, across nine current and ten archived packages.
H006's required-section set is hardcoded to `{"problem statement",
"requirements", "acceptance criteria", "validation matrix"}`, and
`detect_dialect` classifies a repository by scanning for `## ADDED Requirements`
or `#### Scenario:` against `## Acceptance Criteria` plus an `AC-<AREA>-<n>`
match. Neither has been exercised against a five-file corpus, and a repository
that returns `mixed` produces only a plain-print warning from `cmd_detect`
rather than a finding.

A second gap is documentary rather than behavioural: `README.md` states the
rule count as fifteen, while `rules.py`, `CHANGELOG.md`, `tests/baseline_rules.json`,
`docs/next-steps.md` and `docs/agents-skills-harness.md` all agree on sixteen
(G001–G005, H001–H006, U001–U005; there is no G006). The code is right and the
README is stale.

## What Changes

- Add an external-target validation corpus: run `detect` and `validate` with
  `--target` pointed at a clone of `ianshank/Agents` and at a synthetic fixture
  repository, and record the resulting `StackProfile` and finding triage.
- Add a synthetic fixture repository built on the shape the existing `repo`
  pytest fixture uses — a `Makefile`, a manifest carrying the coverage floor at
  its detected locator, a contract file declaring invariant lines, and an
  `openspec/changes/<change>/specs/<capability>/spec.md` tree — extended to
  cover the five-file package shape.
- Assert read-only behaviour mechanically rather than by inspection, following
  the precedent this repository already set in AC-MP-2: patch `subprocess.run`
  and `Popen` to raise, patch socket creation to raise, and compare a tree hash
  before and after.
- Correct the stale rule count in `README.md`.
- File any false positive discovered against either target as its own change
  package, following `fix-u004-body-blind-modal-check` and
  `fix-coverage-floor-detection-gap`.

## Non-Goals

- **No authoring verb.** `tests/test_cli_surface.py` fails the build if any of
  `propose`, `apply`, `chat`, `generate`, or `draft` appears, and
  `docs/next-steps.md` item 6 rejects autonomous spec generation. This change
  does not relax that, and planlint INV-16 — the evaluator proposes nothing —
  is preserved.
- **No shelling out.** `machinery.py`'s docstring requires that it never import
  or call `subprocess`, `os.system`, or any process-execution mechanism. This
  change adds tests that enforce that property, not code that weakens it.
- **No change to the dialect taxonomy.** Whether a five-file corpus should
  produce a new dialect, or a finding, or nothing at all, is a question this
  change answers with evidence rather than a decision it pre-commits.
- **No target repository under legal hold.** Deliberately out of scope; see the
  companion package in the `edge-ai-vii` tree.

## Affected Capabilities

- `external-target-validation`
