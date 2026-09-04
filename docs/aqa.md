# AQA — Automated Quality Assurance

The full quality bar runs from one command: **`make pre-pr`**. It composes the
core `make ci` gate with the enterprise gates (typecheck, security, docs).

## Gates

| Command | What it checks | Failure mode |
|---|---|---|
| `make test` | pytest + line & branch coverage + generated-artifact freshness + detection-corpus labels + matcher-accuracy floors | below floor, a stale rule catalog / plugin manifest, a mislabelled corpus shape, or a matcher under its floor → exit 1 |
| `make lint` | ruff across `openspec_graph`, `tests`, `tools` | any violation → exit 1 |
| `make typecheck` | mypy (config in `pyproject.toml`) | type error → exit 1 |
| `make security` | gitleaks (or deterministic fallback) | committed secret → exit 1 |
| `make validate` | `planlint validate --fail-on ERROR` | spec rule violation → exit 1 |
| `make docs-check` | required docs exist + linked from README | missing/unlinked → exit 1 |
| `make pre-pr` | all of the above + no-hardcoded-thresholds | any → exit 1 |

`make skill-artifacts` (and its halves `make skill-catalog` and `make
skill-manifests`) are **writers, not gates** — they regenerate the distributable
skill's rule catalog and the `.claude-plugin/` manifests. They are deliberately
absent from the table above because they never fail: staleness is caught by
`make test`, which is where a gate belongs.

## Quality-gate thresholds live in config, not in CI

Coverage floors are read from `pyproject.toml` at run time by
`tools/check_coverage_floor.py` (line, `fail_under`) and
`tools/check_branch_coverage.py` (branch, `branch_fail_under`), and the four
`[tool.specgraph]` `*_pct` matcher-accuracy floors by `tools/matcher_accuracy.py`
through the same `_common.read_pyproject_int` helper. Every file
under `.github/workflows/` is scanned for a re-introduced literal, not just
the continuous-integration one. The Makefile
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

The Claude Code dev-tooling this repo is developed with (`.claude/agents/`,
`.claude/skills/`) gets the same discipline, not a documentation-only
exemption: `tests/test_agent_skill_docs.py` parses each agent/skill file's
frontmatter, resolves every backtick-quoted repo-relative path reference and
`` `make <target>` `` reference against what actually exists, and checks
`planlint-add-rule/SKILL.md`'s rule-family checklist against
`openspec_graph/rules_*.py` directly — the exact drift class found (that
checklist silently missing `rules_speckit.py` after the SpecKit dialect
landed) during the review that added this test.

The same argument extends outward to everything an external reader acts on.
`tests/test_agent_artifacts.py` holds the evaluation suite, `context7.json`,
`llms.txt` and the Docker build context to their structural contracts, and
`tests/test_adopter_urls.py` holds *adopter-facing prose* to packaging
metadata: every install command must name the distribution this tree actually
builds, and the version floor the CI template hands an adopter must equal the
one the Agent Skill enforces. That test exists because the opposite happened —
the project was renamed and eight places went on printing an install command
for a distribution that no longer existed, with every gate green, because
nothing compared prose against `pyproject.toml`.

## Two-track e2e

"End-to-end" here means two deliberately different things, and both run:

- **With mocks** — `make test`. Fixture repositories built in `tmp_path`,
  edge conditions simulated with `monkeypatch` (no git binary, corrupt
  witness files, unreadable specs), and the CLI driven both in-process
  (`cli.main()`) and as a real subprocess (`tests/support.py::run_cli`,
  with coverage tracked across the subprocess boundary). This is the fast,
  hermetic track.
- **Without mocks** — `make e2e-live`. The *installed* `planlint` against
  *this live repository*, with zero fixtures: `detect`,
  `validate --fail-on ERROR`, `graph --format json`, `waivers`, and one
  more `validate` pass under `PYTHONIOENCODING=ascii` — the console
  environment that crashed `validate` before the stdout-encoding fix. This
  is the track that catches what fixtures can't: drift between the repo
  and its own specs, encoding/path behavior of the real host, and
  packaging-level breakage.

CI runs the mock track on both operating systems (`test` on Ubuntu 3.10–
3.13, `test-windows` on Windows 3.12) and the live track twice
(`self-validate`, and `encoding-stress` under an ASCII-only console). A
job missing from `docs/hooks.md`'s CI table is a test failure
(`test_hooks_ci_table_lists_every_ci_job`), not a doc gap.

No `make` on your Windows box? Every recipe is two commands; run them
directly, or use Git Bash (make installs via `choco install make -y`,
which is what `test-windows` does).

## Matcher accuracy is a measured number, not a claim

Two rules read English prose rather than repository structure: **G002** (does a
criterion name a non-success outcome) and **U004**/**S003** (is a requirement
normative). Coverage proves their code runs and the one-fixture-per-rule map
proves each *can* fire. Neither says how often either fires on the wrong
sentence — and the README's "And what it got wrong" section records that two
of the four shipped linter faults were exactly that.

`tests/fixtures/phrasing/` is a hand-labelled corpus; `tools/matcher_accuracy.py`
scores the real matcher against it and `tests/test_matcher_accuracy.py` holds
the result to floors declared in `pyproject.toml` `[tool.specgraph]`. The
floors are config, never Make or workflow YAML, because rule G003 says so and
`tools/check_no_hardcoded_thresholds.py` enforces it against this repo too.

| Rule | Precision | Recall | Before tiering |
|---|---|---|---|
| G002 | 0.919 | 0.983 | 0.38 / 0.42 |
| U004 | 0.875 | 1.000 on the SHALL/MUST contract | 0.47 / (0.39 counted the eleven modal-variant rows now set aside; a word-boundary tightening cannot raise recall and did not) |

Read those with the corpus README's three caveats: the negative examples were
written adversarially, eleven sentences could not be labelled confidently and
are excluded from every score, and the corpus is synthetic. It is a regression
net, not a benchmark.

Why it matters most for G002: the rule asks only whether a spec carries **at
least one** non-success criterion, so a single false positive anywhere in the
document switches it off for that document. Under the old flat pattern list,
"The block renders below the header" satisfied it.

`make matcher-accuracy` prints the per-pattern true/false-positive
breakdown and checks the floors; it is a **report**, the same way
`make graph` is, and the gate is `tests/test_matcher_accuracy.py` inside
`make test`. A pattern that misfires more often than it fires is not a
detector, and `test_no_negation_pattern_misfires_more_than_it_fires` fails if
one is added. `.claude/skills/planlint-add-phrasing-case/SKILL.md` is the
checklist for adding a sentence or a pattern.

## Property-based tests

`tests/test_properties.py` states five invariants over the parsers that read
untrusted text — determinism and sorted, unique output; never raising on
arbitrary unicode; idempotent `define` stripping; a requirement count
independent of heading depth; and case-insensitive negation detection.

`derandomize=True` is deliberate. This is a merge gate, and a gate that fails
one run in fifty gets overridden and then deleted, so the example set is fixed
and any failure is reproducible from its message alone. Widening the search is
an explicit local act:

```bash
pytest tests/test_properties.py --hypothesis-seed=random
```

A counterexample found that way belongs in the example suite as a named
regression test, the way the four documented linter faults are.

Mutation testing was evaluated alongside this and **not** adopted: the
measurement was cancelled before producing kill/survive counts, and what it
did establish is that `mutmut` cannot run here without deselecting two of this
repo's own self-checks (`test_new_modules_stdlib_only` rejects its injected
import; `test_typecheck_passes_on_clean_repo` fails under the mutant
trampolines). Adopting it needs its own change package and a real measurement.

## Detection is held to a labelled corpus

`detect` is the load-bearing primitive — G003's threshold locator, G004's
target existence, G005's invariant source and H001's runnable stage are each
only as correct as the dialect card underneath them — and it had been
validated against two real repositories plus inline fixtures. A probe over
twenty synthetic target repositories found five wrong detections and two
crashes, including a UTF-8 BOM that produced a **false G004** against a valid
repository.

`tests/corpus/targets/` now holds labelled target repositories, each with the
card a correct detector should produce, consumed by `tests/test_detect_corpus.py`
through `dialect_card.diff_cards()`. Because that function ignores fields
absent from the baseline, each shape asserts only its own dimension and an
additive schema change does not churn every fixture.

The hostile-Makefile shape is the one that matters most: a specimen whose
`$(shell rm -rf …)`, bare `$(shell touch …)` and `$(eval $(shell …))` would
fire at parse time under real GNU Make — even under `make -n`, confirmed by a
control run — is parsed with a canary directory in place, and the canary is
asserted intact afterwards. That turns "parsing never executes" from a
code-review claim and an import guard into a behavioural assertion.

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

One gate `make pre-pr` cannot reproduce: a `v*` tag additionally runs
`.github/workflows/release.yml`, which builds the wheel, installs it into an
empty virtualenv, and runs the `planlint` **console script**. The test suite
only ever invokes `python -m openspec_graph.cli`, so nothing else exercises the
script a user actually gets, or proves the wheel really needs no runtime
dependencies. Reproduce it locally with:

```bash
python -m build
python -m venv /tmp/smoke && /tmp/smoke/bin/pip install dist/*.whl
/tmp/smoke/bin/planlint --version
```
