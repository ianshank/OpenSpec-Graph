# Spec: Decompose God Files

> **Change:** `decompose-god-files`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

A god-file scan found that responsibility boundaries are not reflected in module
boundaries: five production modules bundle unrelated concerns and four test
modules redeclare the same inline fixtures. The concentration raises the cost of
the next change, even though every gate is green. The decomposition is
structural only — the public API, CLI output, and graph JSON stay byte-identical.

**Evidence:**
- `parse.py` holds two dialect grammars, the shared data model, waiver parsing,
  threshold linting, and heading-drift analysis.
- `rules.py` holds every rule across three families, the driver, and finding
  rendering/serialization.
- `scaffold.py` mixes document templates with filesystem writes.
- `graph.build_graph` is a single function occupying most of its file.
- Four test files redeclare the same `MAKEFILE` / `PYPROJECT` / spec fixtures.

---

## Requirements

- R-DG-1: The public import surface (`openspec_graph.__init__`, `parse.*`,
  `rules.*`) must be unchanged so external and test imports keep working.
- R-DG-2: CLI and graph JSON output must be byte-identical for representative
  fixtures before and after decomposition.
- R-DG-3: New modules must be stdlib-only (no new runtime dependencies).
- R-DG-4: Genuinely-duplicated test helpers must be extracted to a shared
  `tests/support.py`; tailored per-test fixture variants stay inline where used
  (they are not duplicates — each asserts behavior specific to its variant).
- R-DG-5: Import boundaries must be enforced — parser modules must not import
  `cli` or `graph`; rule modules must not import `cli` or `graph`.
- R-DG-6: `detect.py` and `cli.py` are out of scope for this pass.

---

## Acceptance Criteria

- [ ] **AC-DG-1:** `from openspec_graph import build_graph`,
  `from openspec_graph.parse import ParsedSpec, Requirement, Criterion, parse_spec`,
  and `from openspec_graph.rules import Finding, Rule, evaluate, rule_table` all
  succeed unchanged (R-DG-1).
  _Verified by:_ `pytest -k public_import_compatibility` · stage: `make test`

- [ ] **AC-DG-2:** For representative fixtures, `validate --json`,
  `graph --format json`, and `rules --json` output is byte-identical before and
  after decomposition (R-DG-2).
  _Verified by:_ `pytest -k output_byte_identical` · stage: `make test`

- [ ] **AC-DG-3 (non-success):** A moved symbol that changes the ordering of
  `rules --json` output fails `make test` (R-DG-2).
  _Verified by:_ `pytest -k rules_json_ordering_stable` · stage: `make test`

- [ ] **AC-DG-4:** All new modules import only stdlib packages; a third-party
  import in any new module fails `make test` (R-DG-3).
  _Verified by:_ `pytest -k new_modules_stdlib_only` · stage: `make test`

- [ ] **AC-DG-5:** The duplicated `_write_spec` helper is extracted to
  `tests/support.py` and imported (not redeclared) by every test module that uses
  it (R-DG-4).
  _Verified by:_ `pytest -k helpers_not_duplicated_inline` · stage: `make test`

- [ ] **AC-DG-6 (non-success):** Parser modules importing `cli` or `graph`, or
  rule modules importing `cli` or `graph`, fails `make test` (R-DG-5).
  _Verified by:_ `pytest -k import_boundary_discipline` · stage: `make test`

- [ ] **AC-DG-7:** `make pre-pr` is green (ruff, mypy, coverage floors, security,
  docs, no-hardcoded-thresholds, planlint validate) after decomposition
  (R-DG-1, R-DG-3, R-DG-5).
  _Verified by:_ `make pre-pr` · stage: `make pre-pr`

- [ ] **AC-DG-8 (non-success):** No new module named `detect_*` or `cli_*` is
  added; `detect.py` and `cli.py` remain single unsplit files. A split that
  fragments either fails `make test` (R-DG-6).
  _Verified by:_ `pytest -k detect_and_cli_remain_unsplit` · stage: `make test`

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Tests | `make test` | AC-DG-1, AC-DG-2, AC-DG-3, AC-DG-4, AC-DG-5, AC-DG-6, AC-DG-8 |
| Full gate | `make pre-pr` | AC-DG-7 |

---

## Non-Success Criteria (what this change rejects)

- This change does **not** atomize `detect.py` into five tiny detector modules.
  `StackProfile` is a natural aggregate; only a dataclass extraction would be
  considered, and not in this pass.
- This change does **not** split the four large test files by subsystem. Those
  files use tailored fixture *variants* (not duplicates), so consolidating them
  is risky and would violate the byte-identical-output guarantee; test-file
  decomposition is deferred to a separate change package.
- This change does **not** split `cli.py` command handlers across modules. It is
  the expected orchestration hub.
- This change does **not** implement an entry-point rule plugin system. The
  `RULES` registry stays a fixed tuple; plugins remain a documented future
  extension in `docs/next-steps.md`.
- This change does **not** introduce a line-count gate. The scan is evidence for
  the change, not a brittle threshold enforced in CI.

---

## Decisions

- **DEC-DG-001 (resolved):** `parse.py` and `rules.py` are kept as facades that
  re-export the public symbols from the new split modules, rather than being
  renamed. This preserves backward compatibility without churn in call sites and
  tests.
- **DEC-DG-002 (resolved):** Test fixtures are centralized before production
  splits, so the production refactor diffs stay small and merge conflicts stay
  isolated.
