# Spec: CLI Positioning

> **Change:** `rename-cli-and-positioning`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

The product's wedge is "the CI gate that fails when a spec cites a gate this
repo does not have." The command name `specgraph` undersells that wedge and
carries the word "graph" the differentiation strategy retires, and there is no
guard preventing authoring verbs from entering the CLI surface.

**Evidence:** `pyproject.toml:[project.scripts]` ships a single `specgraph`
entry point; `README.md` describes the tool as a "dependency graph for specs"
rather than a CI gate; no test asserts the CLI verb set is a closed read/lint
surface.

---

## Requirements

- R-CP-1: The system MUST ship `planlint` as the primary console-script entry
  point.
- R-CP-2: The system MUST keep `specgraph` as a backwards-compatible alias that
  warns to stderr and delegates to `main`, preserving the real exit code so
  existing CI keeps failing on real errors.
- C-CP-1: The rename MUST NOT break existing user contracts — the waiver syntax
  `<!-- specgraph:allow ... -->`, the config file `openspec/specgraph.json`,
  and the `[tool.specgraph]` pyproject section MUST keep the `specgraph` name.
- C-CP-2: Coverage for the change MUST meet the floor declared in
  `pyproject.toml:[tool.coverage.report].fail_under`. No literal threshold may
  appear in this spec or its tests.

---

## Acceptance Criteria

- [ ] **AC-CP-1:** `planlint` is installed as a console script and runs the
  validate verb. (R-CP-1)
  _Verified by:_ `pytest -k test_planlint_module_runs` · stage: `make test`

- [ ] **AC-CP-2:** The legacy `specgraph` alias prints a deprecation to stderr
  and delegates, preserving the exit code — a clean repo exits 0 and a repo
  with a bad stage exits 1 through the alias. (R-CP-2)
  _Verified by:_ `pytest -k test_deprecated_alias` · stage: `make test`

- [ ] **AC-CP-3:** The CLI verb set is the closed read/lint surface
  {detect, init, new, validate, graph, rules}; an authoring verb is rejected.
  (R-CP-1)
  _Verified by:_ `pytest -k test_cli_verbs` · stage: `make test`

- [ ] **AC-CP-4:** README leads with the wedge, a positioning table, and an
  explicit non-goals section. (R-CP-1)
  _Verified by:_ `make docs-check` · stage: `make docs-check`

- [ ] **AC-CP-5 (non-success):** Adding a `propose`/`apply`/chat verb to
  `cli.build_parser` fails `make test`. The CLI must not become an authoring
  framework. (C-CP-1)
  _Verified by:_ `pytest -k test_cli_rejects_authoring_verbs` · stage: `make test`

- [ ] **AC-CP-6 (non-success):** The deprecation warning never leaks into stdout
  JSON output; stdout stays parseable through the alias. (R-CP-2)
  _Verified by:_ `pytest -k test_deprecated_alias_keeps_stdout_parseable` · stage: `make test`

- [ ] **AC-CP-7:** Coverage for the change meets the floor declared in
  `pyproject.toml:[tool.coverage.report].fail_under`, enforced by the test
  gate — no literal threshold is named in this spec or its tests. (C-CP-2)
  _Verified by:_ `make test` · stage: `make test`

## Invariants Touched

- INV-CLI-1: planlint is a linter under `openspec validate`, never an
  authoring framework — preserved, proven by AC-CP-5.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-CP-1..3, AC-CP-5..7 |
| Docs | `make docs-check` | AC-CP-4 |
