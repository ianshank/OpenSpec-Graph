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

## CI hooks (`.github/workflows/`)

| Job | Trigger | Gate |
|---|---|---|
| `test` (3.10–3.13) | push + PR | `make lint` + `make typecheck` + `make test` |
| `self-validate` | push + PR | `planlint validate --fail-on ERROR` (hard) |
| `graph-diff` | PR only | `tools/diff_spec_graph.py` base→head (AC-CH-5/6) |
| `security` | push + PR | gitleaks + no-hardcoded-thresholds (hard) |
| `docs` | push + PR | `make docs-check` (hard) |
| `release` (separate workflow) | `v*` tag | `make pre-pr`, then a clean-venv smoke test of the `planlint` console script, then trusted publishing to PyPI |

`typecheck` runs as a step inside the `test` matrix (so every supported Python
version is type-checked), not as a standalone job.

The `graph-diff` job checks out the PR head SHA (not the synthetic merge
commit) so `merge-base` resolves to the true branch point (DEC-CH-001).

`release` lives in its own workflow file because it is tag-triggered, not
push/PR-triggered. Its clean-venv step is not redundant with the `test`
matrix: the suite runs the CLI as `python -m openspec_graph.cli`, so nothing
else ever exercises the console script a wheel actually installs, or proves
the package really declares no runtime dependencies.

Note that `tools/check_no_hardcoded_thresholds.py` scans **every** file under
`.github/workflows/`, not a named one — a workflow added later would otherwise
escape the guard while it still printed PASS.

## Claude Code hooks (`.claude/hooks/`)

A third, distinct layer from pre-commit/CI above: a
[Claude Code](https://claude.com/claude-code) `PostToolUse(Edit|Write)` hook,
wired in `.claude/settings.json`, that fires inside an agentic coding session
right after a file write — before the agent considers the change done, not at
commit or push time. It targets drift classes that recurred multiple times in
this repo's own history and are easy for an agent (or a human) to forget
mid-edit:

- Editing `skills/planlint-spec-governance/**` or `.claude-plugin/**` → reminds to
  run `pytest tests/test_skill_contract.py tests/test_agent_skill_docs.py`. These
  are prose and metadata an *external* agent acts on, so no other gate catches
  drift in them. The glob names the distributable skill specifically: a bare
  `*/skills/*` also matched `.claude/skills/`, nudging contributors toward a test
  that does not cover their file.
- Editing `openspec_graph/rules.py` or `rules_*.py` → reminds to regenerate
  `tests/baseline_rules.json` and run `tests/test_rule_registry_docs.py`
  (see the `planlint-add-rule` skill below).
- Editing the `Makefile` or a `.github/workflows/*.yml` file → reminds to run
  `make thresholds`.
- Editing anything under `evals/` → reminds to run
  `pytest tests/test_agent_artifacts.py`. The `planlint-add-eval-case` skill
  under `.claude/skills/` carries the full checklist. The suite's structure is asserted,
  not assumed: a case with no README row, or a `regex` grader with no
  `pattern`, grades nothing and still reports a pass.
- Editing `README.md`, `llms.txt`, `AGENTS.md` or `templates/**` → reminds to
  run `pytest tests/test_adopter_urls.py`. This is the drift class that already
  cost this project eight dead install commands: prose and packaging metadata
  disagreed and every gate stayed green, because nothing compared them.
- Editing a change package's `spec.md`
  (`openspec/changes/*/specs/*/spec.md`) → reminds to run
  `planlint validate --fail-on ERROR` before finishing. This file is the
  exact one planlint dialect-sniffs; prose that quotes a dialect's own
  marker strings (e.g. a heading name in backticks, while *documenting* that
  dialect rather than writing it) can misclassify the spec as the dialect it
  merely describes — a self-referential trap this repo has hit more than
  once while writing specs *about* its own dialect grammar.

`.claude/hooks/nudge_rule_registry.sh` implements all four checks via a
single shell script (no `jq` dependency — not guaranteed to be on `PATH` in
every dev environment this repo is used from). Despite the JSON key's name,
`"decision": "block"` does **not** undo the edit — `PostToolUse` fires after
the write already landed — it is `PostToolUse`'s contract for surfacing
`reason` to the agent prominently, i.e. a strong reminder, not an actual
block.

See also `.claude/agents/` (spec-drafter, spec-adversary, planlint-verifier —
this repo's own dogfooded OpenSpec change-package workflow) and
`.claude/skills/planlint-add-rule/` (the step-by-step checklist the first
hook case above points at).

## Adding a custom rule

Adding or changing a rule also requires regenerating the distributable
skill's rule catalog with `make skill-catalog`; `tests/test_skill_contract.py`
fails on a stale one, and the `.claude/` hook nudges for it.

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

## Releasing a skill change

The `.claude-plugin/` manifests carry a `version`, generated from
`openspec_graph.__version__` by `make skill-manifests`. That number is not
decoration: Claude Code caches an installed plugin by version and refreshes it
only when the string changes. A rewrite of `SKILL.md`'s refusal text under an
unchanged version therefore reaches nobody who already installed the plugin --
they keep the cached copy, and the skill they run is not the skill in this
repository.

So: **any change under `skills/` or `.claude-plugin/` ships in a package
release.** A prose-only fix is still a patch bump, and the tag is what
publishes it. `SKILL.md`'s own `metadata.version` mirrors
`openspec_graph.__version__` for the same reason, and
`tests/test_agent_skill_docs.py` fails if the two drift, so there is one number
to bump rather than three to keep in step by hand.

The alternative — omitting `version` from the manifests so Claude Code falls
back to the resolved commit sha — was rejected: the manifests are pinned to the
package version by `AC-SD-7`, and releases here are already tag-driven, so a
sha-tracking plugin would refresh on every unrelated commit to `main` while the
distribution it invokes stayed put.

## Adding a new pure derived-output module

`dialect_card.py`, `ledger.py`, and `mermaid.py` are all the same shape: a
pure, stdlib-only module that projects a data structure some other module
already computed (a `StackProfile`, a `ParsedSpec` tree, `build_graph()`'s
dict) into a derived output — a diffable snapshot, a ledger, a diagram —
without registering a `Rule` or doing its own filesystem/network I/O.
`dialect_card.py` and `mermaid.py` import no sibling module at all;
`ledger.py` imports `detect.to_posix_relative` — a shared pure-formatting
helper, not a data type it consumes — to render its `path` field the same
way every other consumer of that function does.

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
