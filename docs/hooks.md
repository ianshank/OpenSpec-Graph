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
- `planlint validate` (self-dogfooding: the tool validates its own specs)
- `make docs-check` (required docs present + linked from README)
- `make thresholds` (no hard-coded thresholds in the Makefile or workflow YAML)

Every hook is fail-closed: a violation blocks the commit.

## Optional pre-push hook

The commit-time hooks run lint + typecheck + security + validate + docs-check +
thresholds. If you also want to block a broken **push** (catching what CI
would catch, including the full test suite + coverage floor) before it leaves
your machine, install a pre-push hook that runs the one-command gate:

```bash
cat > .git/hooks/pre-push <<'EOF'
#!/usr/bin/env sh
# Run the full enterprise gate before a push reaches CI.
exec make pre-pr
EOF
chmod +x .git/hooks/pre-push
```

This is **optional and not installed by default** — `make pre-pr` runs the full
coverage suite, so it is slower than the commit-time hook. Pre-commit + CI
already cover the common case; the pre-push hook is for contributors who want
a local net before the round-trip to CI.

## CI hooks (`.github/workflows/ci.yml`)

| Job | Trigger | Gate |
|---|---|---|
| `test` (3.10–3.13) | push + PR | `make lint` + `make typecheck` + `make test` |
| `self-validate` | push + PR | `planlint validate --fail-on ERROR` (hard) |
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
planlint rules --json > tests/baseline_rules.json
```

…then add a deterministic test to `tests/`. The baseline test
(`test_rule_set_matches_baseline`) fails if the rule set changes without the
baseline being updated — a conscious decision, not an accident (C-CH-1).

**A whole-tree rule** (a property of the entire spec tree, not one spec —
e.g. G006 "a declared invariant is cited by *some* living spec", or G009's
identical shape for ADRs) can't be expressed as a per-spec `Rule.check` at
all; that signature only ever sees one `ParsedSpec` at a time. Both existing
instances follow the same recipe instead: register an *inert* stub `Rule`
whose `check` always returns nothing (so `planlint rules`/`rules --json`
still lists the ident), then add the real logic as its own block in
`rules.evaluate_tree()` (`rules.py`) — a plain function over
`Sequence[ParsedSpec]`, called once per `validate`/`graph` run, never per
spec. Every whole-tree `Finding` sets `path=` to the entity's own declaring
source, not any one spec's path (`DEC-WL-004`); its `--change` interaction
is an explicit decision, not silence (`DEC-WL-003`/`DEC-AD-004` — does a
`--change`-filtered spec list put this check's correctness at risk, or
not?). `evaluate_tree()` stays two parallel blocks rather than a registry
for two instances; revisit that only if a third whole-tree rule arrives
(`DEC-AD-003`).

## Adding a new pure derived-output module

`dialect_card.py`, `ledger.py`, and `mermaid.py` are all the same shape: a
pure, stdlib-only module that projects a data structure some other module
already computed (a `StackProfile`, a `ParsedSpec` tree, `build_graph()`'s
dict) into a derived output — a diffable snapshot, a ledger, a diagram —
without registering a `Rule` or doing its own filesystem/network I/O. None of
the three imports another sibling module beyond the data types it consumes.

Follow the same shape for a new one:

1. One public function, `to_<thing>(data) -> <output>`, taking a shape the
   caller already has in hand rather than recomputing it.
2. Stdlib-only — no new dependency (`dependencies = []` in `pyproject.toml`
   is a load-bearing product boundary; see `docs/architecture/c4.md`).
3. Deterministic: same input, byte-identical output, every call. Add a
   `test_*_is_deterministic` test alongside the module's other pure-function
   unit tests, and — if the module is reachable from a CLI verb — a second,
   subprocess-level determinism test in `tests/test_enterprise.py` (see
   `test_graph_format_mermaid_is_deterministic` for the pattern).
4. Register the module in `tests/test_decomposition.py::_NEW_MODULES` so the
   decomposition/import-boundary tests cover it.
5. If the module renders a CLI-visible format, wire the dispatch in `cli.py`
   only — the module itself never calls `print`/`sys.exit`/`argparse`.
