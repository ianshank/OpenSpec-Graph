# OpenSpec-Graph

Map and enforce an OpenSpec discipline on a **cloned** repository — mechanically,
not by review prose.

A spec convention written as guidance decays. The same convention expressed as a
linter with an exit code does not. `specgraph` reads what the target repo already
does — its build stages, where its coverage floor actually lives, its invariant
source, which spec dialect it writes — then holds every spec to that, using the
target's own vocabulary rather than an imported one.

It is a **dependency graph for specs**: requirements link to the criteria that
verify them, criteria link to the make stage that runs them, invariants link to
the contract that declares them, thresholds link to the config that gates them.
`validate` fails when a link is broken — an orphan requirement, a criterion that
cites a stage the repo doesn't have, an invariant cited but never declared, a
threshold hard-coded instead of read from its source.

Zero runtime dependencies. Python 3.10+.

```bash
pip install -e .
specgraph --target /path/to/clone detect      # read-only
specgraph --target /path/to/clone init        # pin detected conventions
specgraph --target /path/to/clone new add-thing --capability thing-capability
specgraph --target /path/to/clone validate    # exit 1 on any ERROR
```

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
would produce a criterion nothing can run. `specgraph` picks the stage from the
target's actual Makefile and cites the target's actual threshold locator, so
G003 and G004 below become enforceable rather than aspirational.

Detection is read-only by contract — ``specgraph detect`` is always safe against an
unfamiliar clone.

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
rule you no longer have.

## What it found in a real repository

Run against `ianshank/Mouse-Droid-AGI` (12 specs across 10 change packages),
``specgraph validate` --fail-on WARN` returned exit 1 with these genuine defects:

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
python -m pytest tests/ -q     # 42 passed
```

Every rule has a fixture that violates it and an assertion that the rule fires
on exactly that violation. Additionally: `test_scaffolded_spec_passes_its_own_validator`
generates a package in both dialects and validates it, so the templates cannot
drift from the rules; `test_apply_is_idempotent_and_refuses_to_clobber` proves a
hand-edited spec survives re-running ``specgraph new``.

## Wiring it into CI

``specgraph validate`` is the gate. Add to `.github/workflows/`:

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
      - run: pip install openspec-graph
      - run: `specgraph detect`                       # surfaces drift in the log
      - run: `specgraph validate` --fail-on ERROR     # exit 1 blocks the merge
```

Or as a Make target, so it joins the existing gate ladder:

```make
specs: ## Validate every OpenSpec change package
	`specgraph validate` --fail-on ERROR
```

## Dogfooding

This repo validates its own specs. The `openspec/` tree holds change packages
written in the `harness` dialect, and CI runs `specgraph --target . validate
--fail-on ERROR` as a hard gate — if any spec in this repo violates a rule, the
build fails. The first change package, [`add-graph-export`](openspec/changes/add-graph-export/specs/graph-export/spec.md),
specs a `specgraph graph` verb that emits the dependency graph as JSON; it
carries seven acceptance criteria, two of them non-success paths, and it
validates clean against the rules it will one day implement.

## Design constraints

- **Detection never writes.** `detect` is safe on any clone.
- **Scaffolding never clobbers.** Existing files are skipped unless `--force`;
  `--dry-run` prints the plan and writes nothing.
- **The target's vocabulary wins.** `specgraph` adapts to the repo's dialect,
  stages, and threshold locator. It does not impose Mango's.
- **No dependencies.** Stdlib only, so grafting into an arbitrary repo adds no
  supply-chain surface to the thing being governed.

Upstream OpenSpec conventions: [Fission-AI/OpenSpec concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md).
