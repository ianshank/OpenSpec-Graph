# Hooks

Pre-commit and CI hooks enforce the same gate as `make pre-pr`, so a commit can
never bypass what CI checks.

## Pre-commit

```bash
pip install pre-commit
pre-commit install
```

`.pre-commit-config.yaml` runs:

- **ruff** (`--fix`) across `openspec_graph/`, `tests/`, `tools/`
- **mypy** across `openspec_graph/`
- **gitleaks** secret scan
- **specgraph validate** (self-dogfooding: the tool validates its own specs)

Every hook is fail-closed: a violation blocks the commit. Hooks are pinned to
the same versions CI uses, so local and CI behavior match.

## CI hooks (`.github/workflows/ci.yml`)

| Job | Trigger | Gate |
|---|---|---|
| `test` (3.10–3.13) | push + PR | `make lint` + `make test` |
| `self-validate` | push + PR | `specgraph validate --fail-on ERROR` (hard) |
| `graph-diff` | PR only | `tools/diff_spec_graph.py` base→head (AC-CH-5/6) |
| `typecheck` | push + PR | `mypy openspec_graph tools` (hard) |
| `gitleaks` | push + PR | gitleaks detect (hard) |

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
