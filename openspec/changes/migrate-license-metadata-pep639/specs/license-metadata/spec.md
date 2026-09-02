# Spec: Licence Metadata

> **Change:** `migrate-license-metadata-pep639`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`pyproject.toml` declared its licence with the deprecated
`license = { text = "Apache-2.0" }` table form. setuptools replaced that with
a PEP 639 SPDX expression plus a `license-files` glob and announced the old
form's removal, so every build warned and some future build would fail — on
whichever runner picked up a newer setuptools first, at whichever moment
someone was trying to cut a release.

**Evidence:** measured directly. `python -m build --wheel` on the pre-change
tree emitted four deprecation warnings, all of them about the licence
declaration; after the migration it emits none. The resulting wheel's
`METADATA` carries `License-Expression: Apache-2.0` and
`License-File: LICENSE`, and the text itself is packaged at
`planlint-0.2.0.dist-info/licenses/LICENSE` — the table form only ever put a
string in the metadata, so this is a substantive change to what ships, not a
rename.

The migration was previously owed and deferred. `docs/next-steps.md` item 15
records it as "attempted and backed out because the SPDX form makes
setuptools require `packaging>=24.2` at build time, which could not be
verified in the environment available (a distro-managed `packaging` 24.0 that
cannot be upgraded)". That premise is stale: `python -m build` resolves
`[build-system] requires` in an isolated environment, installing a modern
setuptools and packaging regardless of what the ambient interpreter ships, so
the ambient version never governs the build the wheel comes from.

The gate this needs is not the obvious one. "A build with no `LICENSE` file
fails" was written down as the fail-closed criterion, tested, and disproved:
setuptools accepts a `license-files` glob matching nothing and produces a
wheel with no licence at all, silently, at exit 0. Nothing in the build
refuses a licenceless distribution, so the only honest gate reads the built
artifact.

---

## Requirements

- R-LM-1: `pyproject.toml` MUST declare its licence as a PEP 639 SPDX
  expression (`license = "Apache-2.0"`) and MUST name the files carrying the
  licence text through `license-files`. The deprecated table form MUST NOT
  remain.
- R-LM-2: `pyproject.toml`'s `[build-system] requires` MUST name a setuptools
  floor that understands both the SPDX string and the `license-files` key,
  and that floor MUST be raised in the same commit as the form switch. A
  floor without the new form buys nothing; the new form without the floor
  fails to build on an old setuptools rather than merely warning.
- R-LM-3: No `License ::` trove classifier MUST remain in `classifiers`. PEP
  639 forbids pairing one with an SPDX expression, and a setuptools new
  enough to honour the expression rejects the pair.
- R-LM-4: The built wheel's `METADATA` MUST carry a `License-Expression`
  matching the expression `pyproject.toml` declares, and a `License-File`
  entry for each declared file; each such file MUST be packaged under the
  distribution's `.dist-info/licenses/` directory and MUST be non-empty.
- R-LM-5: A repeatable gate MUST read every built wheel and fail when the
  SPDX expression is missing or mismatched, when a legacy `License ::`
  classifier survives, or when a declared licence file is absent or empty.
  The gate MUST read the expected expression from `pyproject.toml` rather
  than restating it, so it cannot drift from the source of truth.
- R-LM-6: That gate MUST publish a three-way exit contract: 0 clean, 1 on a
  violation, 2 when the check could not run. "Nothing to check" — an empty
  distribution directory, a directory that does not exist, or a project
  declaring no expression — MUST be exit 2, never exit 0.
- R-LM-7: The gate MUST be invocable as a `make` target, MUST run on every
  pull request rather than only on a tag, and MUST run in the release
  workflow before any artifact is uploaded.
- R-LM-8: A wheel build MUST emit no licence-related deprecation warning.
- R-LM-9: The reason the previously-recorded blocker no longer applies MUST
  be written down where the blocker was recorded, so a future reader does not
  re-derive it or re-defer the work.
- C-LM-1: The licence itself MUST NOT change. The project stays Apache-2.0
  and `LICENSE` keeps its text and its path; this changes how the licence is
  declared, not what it is.
- C-LM-2: The gate MUST NOT add a dependency. It MUST import only the
  standard library plus this repository's own `tools/` helpers, and MUST run
  on the project's declared Python floor — where `tomllib` is absent from the
  stdlib, so it MUST NOT parse TOML.
- C-LM-3: The distribution's other metadata MUST NOT move. Name, version,
  console script, `requires-python`, and the remaining classifiers stay as
  they are.

---

## Decisions

- **DEC-LM-001:** the fail-closed criterion is an **artifact** check, not a
  build check, because the obvious build check is false. The criterion first
  written down was "a build with no `LICENSE` file fails." It was tested and
  it does not: setuptools accepts a `license-files` glob matching nothing,
  emits no error and no warning, and produces a wheel carrying no licence at
  all, at exit 0. A criterion that cannot fail is worse than no criterion,
  because it reads as coverage. So the gate opens the wheel and asserts what
  must be inside it — the only place the property is observable. This is
  recorded rather than quietly replaced: the false criterion is the single
  most useful thing this change learned, and a future reader who reasons
  their way back to "surely the build catches this" needs to find the answer
  already here.
- **DEC-LM-002:** "nothing to check" exits **2**, not 0. A release job whose
  build step silently produced no wheel — a changed `--outdir`, a failed but
  unchecked build, a glob that stopped matching — would sail through a gate
  that treats an empty list as an empty violation list. The same reasoning
  applies to a missing directory and to a `pyproject.toml` declaring no
  expression at all. Exit 2 is this project's existing "the command could not
  run" code (`DEC-SD-001`, `DEC-RE-001`), so the gate publishes the same
  three-way contract the CLI does rather than inventing a second convention
  for the same distinction.
- **DEC-LM-003:** the gate reads the expected expression **from
  `pyproject.toml`** instead of restating `"Apache-2.0"` as a literal. Two
  literals with nothing binding them is the drift class this repository has
  already been bitten by and already tests against elsewhere; a gate that
  hard-codes the answer stops being a check the moment the project relicenses
  and starts being a second thing to remember to edit. It scans the file line
  by line rather than parsing it, because the project targets a Python
  version where `tomllib` is not in the stdlib and it has no runtime
  dependencies to spend on a backport for one script — the same reasoning the
  existing threshold scanners in `tools/` already use, so this adds no new
  precedent.
- **DEC-LM-004:** the gate runs in a new `packaging` job on **every pull
  request**, not only on a tag. Licence metadata is observable only in a
  built artifact, and the release workflow was the only place that ever built
  one — so a packaging regression could not surface until a tag had already
  been pushed, against an index whose versions are immutable and whose
  mistakes therefore cannot be corrected in place, only superseded. Running
  the same script in the release workflow too, before the upload step, is
  deliberate duplication: the PR job catches the regression early, and the
  release step is the one that is load-bearing when someone tags from a
  branch that never opened a PR.
- **DEC-LM-005:** the recorded blocker is dismissed on a checked premise, not
  waved away. `docs/next-steps.md` item 15 backed the migration out because
  "the SPDX form makes setuptools require `packaging>=24.2` at build time,
  which could not be verified in the environment available (a distro-managed
  `packaging` 24.0 that cannot be upgraded)". The premise is stale rather
  than wrong-in-principle: `python -m build` provisions an isolated build
  environment from `[build-system] requires`, which installs a modern
  setuptools and its own packaging dependency there, so the ambient
  interpreter's distro-managed version never participates in the build the
  wheel comes from. Confirmed empirically by the end-to-end build the test
  suite runs. Item 15's other instruction — raise the floor in the same
  commit as the form switch — is followed rather than dropped. Item 15 on
  disk still opens by asserting the table form is in use, which the shipped
  `pyproject.toml` now contradicts; correcting that text is the one roadmap
  edit this change owes and is tracked by `AC-LM-9` rather than assumed done.
- **DEC-LM-006:** the `License :: OSI Approved :: Apache Software License`
  classifier is **removed**, not kept alongside the expression. Keeping both
  was never an option under PEP 639, which forbids the pair outright, and a
  setuptools new enough to honour the SPDX string rejects it rather than
  warning — so "keep it for older tooling" would trade a warning for a build
  failure. A comment is left in `classifiers` recording the deliberate
  absence, because a missing classifier looks exactly like an oversight to
  the next contributor scanning that list.
- **DEC-LM-007:** the violation cases are exercised against **synthetic,
  in-memory wheels**, one per violation, with a single end-to-end test
  building this project for real. A gate is only worth having if something
  proves it rejects a bad artifact, and a real build cannot be asked to be
  broken in six different ways on demand; synthesising the archive is both
  faster and stricter. The end-to-end test is what stops the synthetic
  fixtures drifting into a wheel shape setuptools no longer emits. It skips
  rather than fails when `python -m build` is unavailable or the network
  cannot resolve build requirements — a missing tool is not a licensing
  defect — while CI's own `packaging` and release jobs run that path
  unconditionally, so the skip cannot hide a real failure where it matters.
- **DEC-LM-008:** the gate reads wheels only, not sdists. Both carry the same
  declaration through the same code path, so a second archive reader would
  double the script's surface for a case no evidence points at; the wheel is
  also the artifact the release workflow's smoke test installs, which makes
  it the one whose contents a user actually receives. Revisit if an sdist-only
  defect is ever observed.

---

## Acceptance Criteria

- [x] **AC-LM-1:** `pyproject.toml` declares the SPDX expression and the
  `license-files` glob, its build-system floor is a setuptools that
  understands both, no `License ::` classifier remains, and a real
  `python -m build --wheel` of this project emits no deprecation warning and
  passes the gate. (R-LM-1, R-LM-2, R-LM-3, R-LM-8)
  _Verified by:_ `pytest -k test_the_real_wheel_passes_the_gate` · stage: `make wheel-check`

- [x] **AC-LM-2:** the built wheel's `METADATA` carries a
  `License-Expression` matching the project's declaration and a
  `License-File` entry for each declared file, and the text is packaged,
  non-empty, under the distribution's `.dist-info/licenses/` directory.
  (R-LM-4)
  _Verified by:_ `pytest -k "test_a_correct_wheel_passes or test_the_real_wheel_passes_the_gate"` · stage: `make test`

- [x] **AC-LM-3:** the gate catches every violation it claims to — a missing
  `License-Expression`, an expression that does not match the project's
  declaration, a surviving legacy `License ::` classifier, a declared licence
  file that was not packaged, a packaged licence file that is empty, and an
  archive with no `.dist-info/METADATA` at all — and reports none of them
  against a correct wheel. (R-LM-5)
  _Verified by:_ `pytest -k "test_missing_license_expression_is_caught or test_a_mismatched_expression_is_caught or test_a_legacy_license_classifier_is_caught or test_a_missing_license_file_is_caught or test_an_empty_license_file_is_caught or test_a_wheel_without_metadata_is_caught or test_a_correct_wheel_passes"` · stage: `make test`

- [x] **AC-LM-4 (non-success):** "nothing to check" never reads as
  "everything passed". An empty distribution directory and a directory that
  does not exist each exit **2**, a wheel with a violation exits **1**, and a
  correct wheel exits **0**. (R-LM-6, DEC-LM-002)
  _Verified by:_ `pytest -k "test_main_exits_2_when_there_is_nothing_to_check or test_main_exits_2_on_a_missing_directory or test_main_exits_1_on_a_bad_wheel or test_main_exits_0_on_a_good_wheel"` · stage: `make test`

- [x] **AC-LM-5 (non-success):** the obvious criterion is false and is not
  relied on. A build whose `license-files` glob matches nothing does **not**
  fail: setuptools emits a wheel with no licence, silently, at exit 0 — so
  the absence of a licence is caught by the artifact gate, never by the
  build. The gate does catch exactly that wheel. (R-LM-5, DEC-LM-001)
  _Verified by:_ `pytest -k "test_a_missing_license_file_is_caught or test_main_exits_1_on_a_bad_wheel"` for the gate half · stage: `make test`; the build half is a manual measurement recorded in `DEC-LM-001`, since a test asserting that a build *succeeds* wrongly would pin setuptools' defect as a contract

- [x] **AC-LM-6:** the gate is reachable three ways and cannot be skipped by
  the path a release actually takes: `make wheel-check` builds and checks
  locally, a `packaging` job in `.github/workflows/ci.yml` builds and checks
  on every pull request, and a step in `.github/workflows/release.yml` checks
  before anything is uploaded. (R-LM-7, DEC-LM-004)
  _Verified by:_ manual review of the `Makefile` and both workflow files — no automated wiring check covers workflow job contents for this gate · stage: `make ci`

- [x] **AC-LM-7 (non-success):** nothing but the declaration changed. The
  project is still Apache-2.0 with `LICENSE` unmoved and its text intact —
  the gate compares the packaged copy against the project's own declaration
  and rejects an empty one — and the distribution's name, version, console
  script and remaining classifiers are untouched. (C-LM-1, C-LM-3)
  _Verified by:_ `pytest -k "test_the_real_wheel_passes_the_gate or test_version_has_a_single_source or test_installed_distribution_version_matches_the_package_attribute"` · stage: `make test`

- [x] **AC-LM-8 (non-success):** the gate adds no dependency. Importing
  `tools/check_wheel_metadata.py` under the project's own interpreter pulls
  in nothing beyond the standard library and `tools/_common.py`, so a
  third-party import would fail test collection rather than passing silently
  on a developer machine that happens to have it. (C-LM-2, DEC-LM-003)
  _Verified by:_ `pytest -k test_a_correct_wheel_passes` (the module is imported at collection time) · stage: `make test`, with `make lint` and `make typecheck` covering `tools/` for the rest

- [x] **AC-LM-9:** the dismissed blocker is written down where the blocker
  was recorded: `docs/next-steps.md` item 15 states that the migration
  landed and that the isolated-build-environment argument is what retired the
  `packaging` premise, and `CHANGELOG.md`'s `[Unreleased]` section records
  the metadata change, the new gate, and the false criterion. (R-LM-9,
  DEC-LM-005)
  _Verified by:_ manual review — item 15 still carries its pre-migration text and is outstanding · stage: `make docs-check`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-LM-2..5, AC-LM-7, AC-LM-8 |
| Packaging | `make wheel-check` | AC-LM-1 — a real isolated build, gated |
| Core | `make ci` | AC-LM-6, plus lint and this repo's own `planlint validate` |
| Docs | `make docs-check` | AC-LM-9 (manual review; no automated content check covers the roadmap prose) |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
