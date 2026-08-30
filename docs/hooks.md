# Hooks

Pre-commit and CI hooks enforce the same gate as `make pre-pr`, so a commit can
never bypass what CI checks.

## Pre-commit

```bash
pip install -e ".[dev]"
pip install pre-commit
pre-commit install
```

`.pre-commit-config.yaml` uses **local hooks that call `make`** — the same
targets CI uses — so a commit can never bypass CI and there is no second set of
tool-version pins to drift from the dev extras:

- `make lint` (ruff) across `openspec_graph/`, `tests/`, `tools/`
- `make typecheck` (mypy) across `openspec_graph/`, `tools/`
- `make security` (gitleaks or fallback)
- `specgraph validate` (self-dogfooding: the tool validates its own specs)

Every hook is fail-closed: a violation blocks the commit.

## CI hooks (`.github/workflows/ci.yml`)

| Job | Trigger | Gate |
|---|---|---|
| `test` (3.10–3.13) | push + PR | `make lint` + `make typecheck` + `make test` |
| `self-validate` | push + PR | `specgraph validate --fail-on ERROR` (hard) |
| `graph-diff` | PR only | `tools/diff_spec_graph.py` base→head (AC-CH-5/6) |
| `security` | push + PR | gitleaks + no-hardcoded-thresholds (hard) |
| `docs` | push + PR | `make docs-check` (hard) |

`typecheck` runs as a step inside the `test` matrix (so every supported Python
version is type-checked), not as a standalone job.

The `graph-diff` job checks out the PR head SHA (not the synthetic merge
commit) so `merge-base` resolves to the true branch point (DEC-CH-001).

## Adding a custom rule

Rules live in `openspec_graph/rules.py` as `Rule(ident, severity, dialects,
summary, check)`. A rule is a pure function
`(ParsedSpec, StackProfile) -> Iterable[str]` that yields one message per
violation. Add the `Rule` to the `RULES` tuple, regenerate the baseline:

```bash
specgraph rules --json > tests/baseline_rules.json
```

…then add a deterministic test to `tests/`. The baseline test
(`test_rule_set_matches_baseline`) fails if the rule set changes without the
baseline being updated — a conscious decision, not an accident (C-CH-1).
