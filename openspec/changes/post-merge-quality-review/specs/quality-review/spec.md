# Spec: Post-Merge Quality Review

> **Change:** `post-merge-quality-review`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

The merged `enterprise-hardening` branch passed its own gates but an objective
peer review surfaced minor hygiene debt: ruff findings outside the default rule
set, `mypy --strict` type-arg gaps, an uncovered unknown-log-level branch,
duplicated repo-root discovery across gate scripts, a magic number in the public
graph JSON contract, and a missing documented pre-push hook. These are not
correctness bugs; they are the kind of debt that compounds if left for the next
contributor.

**Evidence:**
- `ruff --select B,SIM,RET,UP,RUF,PTH,...` → 2 findings (`SIM105`, `RET504`).
- `mypy --strict openspec_graph` → 3 `type-arg` errors in `graph.py`.
- Coverage: `log.py:28`, `graph.py:160-161`, `rules.py:47-48`, `cli.py:62`,
  `cli.py:72-73` uncovered (targeted, not exhaustive).
- `grep` for `Path(__file__).resolve().parent.parent` → 3 identical copies.

---

## Requirements

- R-PR-1: Lint and type-check config must enforce the rules already adopted;
  trivial findings flagged by extended ruff families must be fixed, not
  grandfathered.
- R-PR-2: Public graph JSON contract values must not be magic numbers; the
  node-text truncation limit must be a named, documented constant.
- R-PR-3: Shared logic across gate scripts must be extracted to a reusable,
  stdlib-only helper so a fix to repo-root discovery is made once.
- R-PR-4: High-risk uncovered branches must have targeted edge-case tests —
  unknown log level, path-outside-root fallback, dry-run, mixed dialect —
  without chasing 100% coverage.
- R-PR-5: Reusable extension points (skills/agents, hooks/loops) must be
  identified and documented as deliberate deferrals, not silently absent.

---

## Acceptance Criteria

- [x] **AC-PR-1:** The default `make lint` ruff config is clean, AND the
  extended ruff families (run as an advisory diagnostic, not a hard gate) report
  zero findings (R-PR-1).
  _Verified by:_ `make lint` (hard gate) + advisory `ruff check --select B,SIM,RET,UP,RUF,PTH,PIE,C4 openspec_graph tests tools` · stage: `make lint`

- [x] **AC-PR-2:** `mypy --strict openspec_graph` reports zero `type-arg`
  errors (R-PR-1). Advisory diagnostic; the hard gate is `make typecheck`.
  _Verified by:_ `make typecheck` (mypy, hard gate) + advisory `mypy --strict openspec_graph` · stage: `make typecheck`

- [x] **AC-PR-3 (non-success):** The graph node-text truncation is a named
  constant (`NODE_TEXT_LIMIT`); a bare `[:200]` literal in `graph.py` fails
  `make test` (R-PR-2).
  _Verified by:_ `pytest -k graph_has_no_bare_truncation_magic_number` · stage: `make test`

- [x] **AC-PR-4:** The three gate scripts import `repo_root`/`read_text` from a
  shared `tools/_common.py`; a re-introduced `Path(__file__).resolve().parent.parent`
  literal in any of them fails `make test` (R-PR-3).
  _Verified by:_ `pytest -k gate_scripts_have_no_duplicated_repo_root_literal` · stage: `make test`

- [x] **AC-PR-5:** Targeted edge-case tests exist and pass for: unknown
  `SPECGRAPH_LOG_LEVEL` (default fallback), path-outside-root in
  `_relative_to`/`Finding.render`, `init --dry-run`, and mixed-dialect warning
  (R-PR-4).
  _Verified by:_ `pytest -k "level_from_unknown or relative_to_outside"` · stage: `make test`

- [x] **AC-PR-6 (non-success):** `tools/_common.py` is stdlib-only; a third-party
  import introduced into it fails `make test` (R-PR-3).
  _Verified by:_ `pytest -k common_module_is_stdlib_only` · stage: `make test`

- [x] **AC-PR-7:** `docs/next-steps.md` documents the deferred hooks/loops
  (watch loop, scheduled self-validation cron, pre-push hook) and the
  skills/agents extension point (entry-point rule registration), each with the
  reason it is deferred (R-PR-5).
  _Verified by:_ `specgraph validate` · stage: `make pre-pr`

- [x] **AC-PR-8 (non-success):** The pre-push hook is documented as optional and
  not installed by default; a reference to `pre-push` in the Makefile or CI
  workflow fails `make test` (a forced slow pre-push hook is rejected) (R-PR-5).
  _Verified by:_ `pytest -k pre_push_hook_is_not_forced_into_makefile_or_ci` · stage: `make test`

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Lint + type | `make lint` + `make typecheck` | AC-PR-1, AC-PR-2 |
| Tests | `make test` | AC-PR-3, AC-PR-4, AC-PR-5, AC-PR-6, AC-PR-8 |
| Full gate | `make pre-pr` | AC-PR-7 |

---

## Non-Success Criteria (what this change rejects)

- This change does **not** make `mypy --strict` a hard CI gate. The pragmatic
  config (`check_untyped_defs`, `warn_unused_ignores`, `warn_return_any`) stays;
  `--strict` is run as an advisory diagnostic only (DEC-PR-001).
- This change does **not** extract a plugin/entry-point rule-pack system. The 16
  rules remain a fixed tuple; entry-point registration is a documented
  next-steps item, not v0.1 surface (DEC-PR-002).
- This change does **not** chase exhaustive coverage. Only high-risk uncovered branches
  received targeted tests; the `if __name__ == "__main__":` guard and trivial
  display branches are intentionally left uncovered.
- This change does **not** force a pre-push hook. It is documented as optional;
  the Makefile and CI never depend on it.

---

## Decisions

- **DEC-PR-001 (resolved):** `mypy --strict` is advisory, not a gate. The 3
  `type-arg` fixes are applied (low churn, obviously beneficial) but `strict =
  true` is not enabled in `pyproject.toml` because `tools/` would require
  further annotation churn disproportionate to the value for a v0.1 tool.
- **DEC-PR-002 (resolved):** No dynamic rule-pack plugin interface. The rules
  are the reusable "skills" and the evaluator is the harness; the entry-point
  extension point is documented in `docs/next-steps.md` (item 3 / 11) for when
  cross-repo composition is proven necessary.
