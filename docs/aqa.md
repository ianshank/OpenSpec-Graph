# AQA — Automated Quality Assurance

The full quality bar runs from one command: **`make pre-pr`**. It composes the
core `make ci` gate with the enterprise gates (typecheck, security, docs).

## Gates

| Command | What it checks | Failure mode |
|---|---|---|
| `make test` | pytest + line & branch coverage | below floor → exit 1 |
| `make lint` | ruff across `openspec_graph`, `tests`, `tools` | any violation → exit 1 |
| `make typecheck` | mypy (config in `pyproject.toml`) | type error → exit 1 |
| `make security` | gitleaks (or deterministic fallback) | committed secret → exit 1 |
| `make validate` | `planlint validate --fail-on ERROR` | spec rule violation → exit 1 |
| `make docs-check` | required docs exist + linked from README | missing/unlinked → exit 1 |
| `make pre-pr` | all of the above + no-hardcoded-thresholds | any → exit 1 |

## Quality-gate thresholds live in config, not in CI

Coverage floors are read from `pyproject.toml` at run time by
`tools/check_coverage_floor.py` (line, `fail_under`) and
`tools/check_branch_coverage.py` (branch, `branch_fail_under`). The Makefile
and workflow YAML contain **no** quality-gate thresholds (coverage floors) and
no tool-version pins (`ruff==`, `mypy==`, `pytest==`) — tools come from the
`[dev]` extras. `tools/check_no_hardcoded_thresholds.py` fails the gate if a
coverage floor or tool-version pin is re-introduced into the Makefile or
workflow (rule G003 / AC-EH-6).

What is *not* externalized and is intentional: GitHub Action versions
(`actions/checkout@v4`), the Python version matrix, and the Docker base image
(`python:3.12-slim`) are CI/infrastructure pins, not quality thresholds — they
are not in scope of the no-hardcoded-thresholds gate.

A missing floor or uninstrumented source is a **misconfiguration**, not a skip:
the coverage floor scripts exit 2 with a clear message. A missing gate is a bug.

## Deterministic validation

Rule-engine and CLI JSON output is deterministic (AC-EH-4):

- `spec_files` discovery is `sorted()`.
- Findings are appended in rule-then-file order; `validate --json` preserves
  that stable order.
- `graph --format json` builds nodes/edges in deterministic iteration order.
- `graph --format mermaid` (`mermaid.py`, CP-GV) holds to the same contract:
  pure over `build_graph()`'s own dict, so it inherits that determinism
  directly. Proven at both the pure-function level
  (`test_output_is_deterministic_across_repeated_calls`) and the CLI level
  (`test_graph_format_mermaid_is_deterministic`), the same two-level
  coverage `--format json` gets.

Tests (`tests/test_enterprise.py`, `*_deterministic`) assert that re-evaluating
the same fixture tree yields **byte-identical** JSON, so a future change that
introduces set-iteration or unordered dict building fails CI.

Structural Makefile parsing (`machinery.py`) holds to the same contract:
`MakefileFacts.targets` is always a sorted, deduplicated tuple
(`test_makefile_facts_targets_is_a_sorted_deduplicated_tuple`), and it is
additionally never allowed to shell out to `make` under any confidence
level — enforced by both a static import guard
(`test_machinery_never_imports_subprocess`) and a runtime execution test
that monkeypatches `subprocess.run`/`Popen` to raise if called at all. A
component that can't be relied on to behave the same way twice, or that can
execute untrusted input, is not enterprise-gradeable no matter how clean its
output looks on one run.

`detect --format json`'s dialect card (`dialect_card.py`, CP-2) holds to a
stricter version of the same contract: byte-identical not only across two
runs, but across the *same logical repo checked out at two different
absolute paths* — proven directly, not assumed, by
`test_detect_format_json_card_is_identical_across_different_checkout_paths`.
`StackProfile.to_card()` achieves this by excluding every absolute-path
field (`root`, and `openspec_root` reduced to a portable
`has_openspec_root` boolean) that `as_dict()` still carries for backward
compatibility. `detect --diff <prev.json>` diffs two cards field-by-field
(`dialect_card.diff_cards`) and exits non-zero listing exactly what
changed — the same `PASS`/`FAIL` vocabulary as `tools/diff_spec_graph.py`'s
existing graph-diff gate, applied to detected conventions instead of the
spec graph.

## No NumPy / no heavy runtime deps

`planlint` has **zero runtime dependencies**. Scientific-computing stacks
(NumPy, pandas) are not used and not required. `pip install -e .` is sufficient;
`pip install -e ".[dev]"` adds pytest, ruff, and mypy for contributors.

## Reproducing CI locally

```bash
pip install -e ".[dev]"
make pre-pr          # the exact bar CI enforces
planlint --target . validate --fail-on WARN   # warnings too, if desired
```

CI runs the same gates across Python 3.10–3.13, plus a self-validation hard
gate (`planlint` validates its own `openspec/` tree) and a graph-diff
regression gate on PRs.
