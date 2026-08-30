# OpenSpec-Graph (`planlint`)

**The CI gate that fails when a spec cites a gate this repo does not have.**

Point `planlint` at a cloned repository. It reads the target's *real* machinery —
its make targets, where its coverage floor actually lives, its invariant
source, which spec dialect it writes — then holds every spec to that, using the
target's own vocabulary rather than an imported one. A spec that cites
`make regression` in a repo with no `regression` target fails the build. A spec
that hard-codes `85%` when `pyproject.toml` gates `90%` fails the build. A plan
with no non-success criterion fails the build.

A spec convention written as guidance decays. The same convention expressed as a
linter with an exit code does not. `planlint` is a **linter under
`openspec validate`**, not an authoring framework.

It is also a **dependency graph for specs**: requirements link to the criteria
that verify them, criteria link to the make stage that runs them, invariants
link to the contract that declares them, thresholds link to the config that gates
them. `validate` fails when a link is broken — an orphan requirement, a
criterion that cites a stage the repo doesn't have, an invariant cited but never
declared, a threshold hard-coded instead of read from its source.

Zero runtime dependencies. Python 3.10+.

```bash
pip install -e .                     # local dev install (no PyPI release yet)
planlint --target /path/to/clone detect      # read-only: stack, dialect, threshold
planlint --target /path/to/clone init        # pin detected conventions into openspec/
planlint --target /path/to/clone new add-thing --capability thing-capability
planlint --target /path/to/clone validate    # exit 1 on any ERROR — the gate
```

> The package is not yet published to PyPI. Until it is, install from source
> (`pip install -e .`) or directly from GitHub
> (`pip install git+https://github.com/ianshank/OpenSpec-Graph`).

> The command was renamed from `specgraph` to `planlint`. `specgraph` remains a
> backwards-compatible alias that prints a deprecation to stderr and delegates
> (preserving the real exit code), so existing CI keeps working. The waiver
> comment syntax (`<!-- specgraph:allow ... -->`), the config file
> (`openspec/specgraph.json`), and the `[tool.specgraph]` pyproject section keep
> the `specgraph` name as stable contract identifiers.

## Why this and not Spec-Kit / GitHub Spec / Kiro / Cursor

The category is crowded with authoring surfaces. `planlint` is deliberately not
one. Rather than claim feature parity (or gaps) against tools we have not
audited line-by-line, here is the positioning that is actually load-bearing:

| Tool | Primary lane | Boundary |
|---|---|---|
| `planlint` | spec-as-lint in CI (under `openspec validate`) | CLI with an exit code; no UI, no MCP server |
| Spec-Kit | spec storyboarding / validation | CI |
| GitHub Spec | spec editing tied to GitHub | CI / IDE |
| Kiro | spec-driven IDE workflow | IDE |
| Cursor / Gemini CLI | AI coding agents | IDE / CLI |

What `planlint` does that the authoring surfaces do not, by construction:

- Reads the target repo's real machinery (Makefile, `pyproject.toml`, invariant
  source) and holds specs to *that*, using the target's own vocabulary.
- Reads thresholds from the detected locator instead of letting them be
  hard-coded in spec prose (G003).
- Fails closed when a spec cites a gate the repo does not have (G004).

What `planlint` deliberately does **not** do (see Non-goals): author specs, own a
UI, serve MCP, run tests, or carry dependencies.

The wedge is narrow on purpose: **`planlint` is the thing you point at someone
else's clone to prove its specs are executable in that repo.** The moment it
becomes a place people write specs, it enters a feature race with 60k-star tools
and loses.

## Why detection comes first

The two repositories this was built against disagree on nearly everything a
naive template would have hard-coded:

| | `Mango_Code_Agent-Harness` | `Mouse-Droid-AGI` |
|---|---|---|
| spec dialect | `harness` (`AC-<AREA>-<n>` + `_Verified by:_`) | `upstream` (`### Requirement:` + `#### Scenario:`) |
| coverage floor lives in | `harness/shared/governance-policy.json:coverage.lines` | `pyproject.toml:[tool.coverage.report].fail_under` |
| focused gate | `make test-governance` | `make regression` |
| invariants | 17 `INV-n` in `CONTRACT.md` | none declared |
| make targets | 29 | 18 |

A template that emitted `_Verified by: make test-governance` into Mouse-Droid
would produce a criterion nothing can run. `planlint` picks the stage from the
target's actual Makefile and cites the target's actual threshold locator, so
G003 and G004 below become enforceable rather than aspirational.

Detection is read-only by contract — `planlint detect` is always safe against an
unfamiliar clone.

## Non-goals (what this rejects)

- **Not an authoring framework.** No `propose`, `apply`, `chat`, or `generate`
  verb. The CLI surface is a closed set of read/lint verbs; a guard test
  (`tests/test_cli_surface.py`) fails if an authoring verb is added.
- **Not an IDE or a UI.** No editor integration, no dashboard. It is a CLI with
  an exit code, designed to live behind `openspec validate` in CI.
- **Not an MCP server.** It does not expose tools to other agents. It is the
  gate those agents' output must pass.
- **Not a coverage tool.** It reads the coverage floor the repo already
  configures; it does not run tests or compute coverage.
- **No dependencies.** Stdlib only, so grafting into an arbitrary repo adds no
  supply-chain surface to the thing being governed.

## Rules

Prose conventions, mechanized. `ERROR` blocks the gate; `WARN` degrades review
quality without making the document wrong.

| ID | Sev | Dialect | Checks |
|---|---|---|---|
| G001 | ERROR | any | The spec declares something verifiable at all |
| G002 | ERROR | any | At least one criterion names a **non-success** outcome |
| G003 | ERROR | any | No hard-coded thresholds; read them from the detected locator |
| G004 | ERROR | any | Every cited `make <target>` exists in the target's Makefile |
| G005 | WARN | any | Every cited `INV-n` is declared in the invariant source |
| H001 | ERROR | harness | Every AC has `_Verified by:_` naming a runnable stage |
| H002 | WARN | harness | Every AC traces to an `R-`/`C-` requirement |
| H003 | WARN | harness | No orphan requirements (every one is verified by some AC) |
| H004 | ERROR | harness | Criterion IDs are unique |
| H005 | WARN | harness | A `(BLOCKING)` open question keeps `Status: DRAFT` |
| H006 | WARN | harness | Required sections present |
| U001 | ERROR | upstream | An `ADDED`/`MODIFIED`/`REMOVED` delta header is declared |
| U002 | ERROR | upstream | Every requirement has at least one Scenario |
| U003 | ERROR | upstream | Every Scenario is GIVEN / WHEN / THEN |
| U004 | WARN | upstream | Requirements use SHALL / MUST |
| U005 | WARN | upstream | Heading depths match the convention |

G002 is the load-bearing one. It mechanizes the rule from
`docs/specs/SPEC_TEMPLATE.md`: *at least one criterion must name a non-success
outcome — what this change rejects, denies, or fails closed on.* A plan that
only describes success has not said what going wrong looks like.

G003 is the second. Thresholds are a governance input, not a spec literal; a
number typed into a criterion is a number that will drift from the config that
actually gates CI.

### Waivers

Judgement calls stay possible, but stay visible:

```markdown
<!-- specgraph:allow G003 this spec's subject IS the 85% hook floor -->
```

The finding is downgraded to `INFO` and prefixed `[waived]` — it still appears
in the report and in CI logs. It is not deleted. A waiver you cannot see is a
rule you no longer have. The `specgraph:allow` comment syntax is a stable
contract identifier kept under that name for backwards compatibility.

## What it found in a real repository

Run against `ianshank/Mouse-Droid-AGI` (12 specs across 10 change packages),
`planlint validate --fail-on WARN` returned exit 1 with these genuine defects:

- `mouse-droid-nemoclaw-integration/specs/openclaw-integration/spec.md` states
  six requirements (`## REQ 1:` … `## REQ 6:`) and **zero** scenarios — nothing
  verifies any of them (G001, U002 ×6).
- `mouse-droid-doc-reconciliation/specs/docs-governance/spec.md` pins `85%` in
  criterion prose while the repo's real floor is `pyproject.toml` `fail_under =
  90` — exactly the drift G003 exists to catch.
- `mouse-droid-deploy-repin/specs/pin-reachability/spec.md` writes requirements
  at `##` and scenarios at `###`, while its nine sibling packages use `###` and
  `####` (U005), and declares no delta header (U001).
- Twelve requirements across `claude-workforce` and `dev-governance` are titled
  as nouns ("MCP Configuration", "Truthful Coverage Claims") with no SHALL or
  MUST, so they read as topics rather than obligations (U004).

Against `Mango_Code_Agent-Harness`: 0 errors, 4 warnings — every spec in
`add-neurosym-governed-synthesis` goes from `## Problem Statement` straight to
`## Acceptance Criteria` with no `## Requirements` section, so its ACs have
nothing to trace back to (H006).

### And what it got wrong

Three findings in the first run were the linter's fault, not the repo's. They
are now regression tests, named after the file that exposed them:

1. **G002 false positive** on `cloud-egress`. "a partial GCP block **opens no**
   egress channel" is a non-success scenario; the original fixed-phrase detector
   missed it. Replaced with a negation-pattern matcher covering absence
   phrasings (`opens no`, `mutates neither`, `leaves … unchanged`).
2. **Misleading G001** on `pin-reachability`. Reported "no criteria found" when
   the real problem was heading depth. The parser now accepts `##`–`####` for
   requirements and reports the deviation as U005 — blaming the drift, not the
   author.
3. **Unrecognized third form.** `## REQ 1:` parsed as nothing. Now recognized,
   so the report says "6 requirements but no Scenario" instead of silence.

A linter that never fails is a decoration; one that fails wrongly gets disabled.
Both directions are tested.

## Tests

```bash
python -m pytest tests/ -q     # full suite
make ci                         # test + lint + validate (core gate)
make pre-pr                     # full enterprise AQA gate
```

Every rule has a fixture that violates it and an assertion that the rule fires
on exactly that violation. Additionally: `test_scaffolded_spec_passes_its_own_validator`
generates a package in both dialects and validates it, so the templates cannot
drift from the rules; `test_apply_is_idempotent_and_refuses_to_clobber` proves a
hand-edited spec survives re-running `planlint new`.

## Enterprise AQA gate

`make pre-pr` runs the full quality bar in one command — the same bar CI
enforces:

| Gate | Command | Checks |
|---|---|---|
| test | `make test` | pytest + line & branch coverage (floors in `pyproject.toml`) |
| lint | `make lint` | ruff across package, tests, and tools |
| typecheck | `make typecheck` | mypy (config in `pyproject.toml`) |
| security | `make security` | gitleaks (or deterministic fallback) |
| validate | `make validate` | `planlint validate --fail-on ERROR` |
| docs | `make docs-check` | required docs present + linked from README |

No numeric threshold lives in the Makefile or CI YAML — floors are read from
`pyproject.toml` at run time, and `tools/check_no_hardcoded_thresholds.py`
fails the gate if a number is re-introduced. Debug diagnostics go to stderr
only via `--verbose` / `PLANLINT_LOG_LEVEL` (the legacy `SPECGRAPH_LOG_LEVEL` is
still accepted); JSON stdout stays parseable. See [`docs/aqa.md`](docs/aqa.md).

## Wiring it into CI

`planlint validate` is the gate. Add to `.github/workflows/`:

```yaml
name: spec-gate
on: [pull_request]
jobs:
  specs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install git+https://github.com/ianshank/OpenSpec-Graph
      - run: planlint --target . detect                       # surfaces drift in the log
      - run: planlint --target . validate --fail-on ERROR     # exit 1 blocks the merge
```

Or as a Make target, so it joins the existing gate ladder:

```make
specs: ## Validate every OpenSpec change package
	planlint --target . validate --fail-on ERROR
```

## Dogfooding

This repo validates its own specs. The `openspec/` tree holds change packages
written in the `harness` dialect, and CI runs `planlint --target . validate
--fail-on ERROR` as a hard gate — if any spec in this repo violates a rule, the
build fails. The first change package, [`add-graph-export`](openspec/changes/add-graph-export/specs/graph-export/spec.md),
specs a `planlint graph` verb that emits the dependency graph as JSON; it
carries seven acceptance criteria, two of them non-success paths, and it
validates clean against the rules it will one day implement.

## Design constraints

- **Detection never writes.** `detect` is safe on any clone.
- **Scaffolding never clobbers.** Existing files are skipped unless `--force`;
  `--dry-run` prints the plan and writes nothing.
- **The target's vocabulary wins.** `planlint` adapts to the repo's dialect,
  stages, and threshold locator. It does not impose Mango's.
- **No dependencies.** Stdlib only, so grafting into an arbitrary repo adds no
  supply-chain surface to the thing being governed.

## Documentation

- [CHANGELOG](CHANGELOG.md) — releases and notable changes
- [Architecture (C4)](docs/architecture/c4.md) — context, container, component, code
- [AQA guide](docs/aqa.md) — the full quality bar and how to reproduce it
- [Hooks](docs/hooks.md) — pre-commit + CI gates, and how to add a rule
- [Agents, skills, and the harness](docs/agents-skills-harness.md) — why this is
  a deterministic governance harness, not an autonomous agent
- [Next steps](docs/next-steps.md) — what is deliberately out of scope
- [Differentiation roadmap](docs/differentiation-roadmap.md) — the wedge, the
  comparison, and the candidate change packages

Upstream OpenSpec conventions: [Fission-AI/OpenSpec concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md).
