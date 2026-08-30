# Spec: Adopter Artifacts

> **Change:** `fix-adopter-artifact-drift`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

The `rename-cli-and-positioning` change (PR #5) renamed the primary CLI from
`specgraph` to `planlint`, but its own touch map did not include the
artifacts adopters actually copy into their own repos, so they drifted.

**Evidence:** `templates/spec-gate.yml`'s `run:` steps wrap shell commands in
literal backticks, which GitHub Actions' bash reads as command substitution
rather than a literal invocation — on one line the substitution silently
drops the `--fail-on ERROR` flag entirely. The same file installs from a
PyPI name that returns 404. `Dockerfile` and `.pre-commit-config.yaml` still
invoke the deprecated `specgraph` alias in their executable lines. This is
the same class of doc/reality drift the tool exists to catch elsewhere.

---

## Requirements

- R-AA-1: Every command shown in an adopter-facing artifact
  (`templates/spec-gate.yml`, `Dockerfile`, `.pre-commit-config.yaml`) MUST
  invoke the current primary CLI name (`planlint`), not the deprecated
  `specgraph` alias, excluding the identifiers preserved by contract
  (C-AA-1).
- R-AA-2: `templates/spec-gate.yml` MUST contain directly-executable shell in
  every `run:` step, with no stray Markdown code-span syntax carried into the
  YAML.
- R-AA-3: `templates/spec-gate.yml` MUST install the package by a method that
  actually resolves, not a PyPI name that returns a not-found response.
- R-AA-4: Every file path a doc cites as supporting evidence MUST resolve to
  a file that exists in the repository.
- C-AA-1: This change MUST NOT rename the identifiers the CP-1 rename
  explicitly kept as `specgraph`: the waiver comment syntax, the
  `openspec/specgraph.json` config file, the `[tool.specgraph]` pyproject
  section, and pre-commit hook `id:`/`name:` fields.

---

## Acceptance Criteria

- [x] **AC-AA-1:** `templates/spec-gate.yml`'s `run:` steps invoke
  `planlint`, contain no literal backtick characters, and install from a
  source that resolves. (R-AA-1, R-AA-2, R-AA-3)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-AA-2:** `Dockerfile`'s comments and `ENTRYPOINT` invoke
  `planlint`. (R-AA-1)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-AA-3:** `.pre-commit-config.yaml`'s `specgraph-validate` hook's
  `entry:` line invokes `planlint`. (R-AA-1)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-AA-4:** Every file path cited from `README.md` and
  `docs/differentiation-roadmap.md` as supporting a rule or claim resolves
  to a file that exists in the repository. (R-AA-4)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-AA-5 (non-success):** A backtick-wrapped `run:` value or a
  `specgraph` CLI invocation reintroduced into any of the three
  adopter-facing artifacts is not acceptable and does not pass review; this
  spec's own non-success criterion names the failure mode so a future
  reviewer checks for it explicitly. (R-AA-1, R-AA-2)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-AA-6:** The pre-commit hook `id:`/`name:` fields, the waiver
  comment syntax, `openspec/specgraph.json`, and `[tool.specgraph]` remain
  unchanged by this change. (C-AA-1)
  _Verified by:_ manual review · stage: `make docs-check`

---

## Invariants Touched

None — this repo declares no invariant source (`openspec/project.md`:
`Invariant source: (none found)`), so no `INV-n` is cited by this spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Docs | `make docs-check` | AC-AA-1..6 (manual review; no automated content check exists for these files by design — see proposal Non-Goals) |
| Full | `make pre-pr` | No regression in the existing test suite, lint, or type-check gates |
