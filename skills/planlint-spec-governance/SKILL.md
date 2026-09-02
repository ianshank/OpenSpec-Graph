---
name: planlint-spec-governance
description: Validate OpenSpec or SpecKit change packages (proposal.md, spec.md, tasks.md) against a repository's real Makefile targets, coverage floor, waivers and witnesses using the deterministic planlint CLI. Use when asked to validate, lint, check or repair specs or implementation plans, before writing code from a plan, or when a spec-gate CI job fails. Read-only by default; never writes waivers or witnesses.
license: Apache-2.0
compatibility: Requires the planlint CLI (version 0.2.0 or newer) on PATH and Python 3.10 or newer. git is optional.
metadata:
  version: 0.2.0
  planlint-min-version: 0.2.0
---

# planlint spec governance

`planlint` is a deterministic linter for implementation plans. It reads a
repository's real machinery -- Makefile targets, the coverage floor's config
locator, declared invariants -- and reports where a spec's claims do not match
them. It contains no model and makes no judgement calls.

**Your job is to run it and report what it says. The exit code is the verdict.**

## Preflight

Run `planlint --version` first.

- Not found: tell the user to install it (`pip install planlint`) and stop.
  Do not install it on their behalf without being asked.
- Older than the version named in this skill's `planlint-min-version`: say so
  and stop. Older releases lack the exit-code behaviour described below.

## The two commands that do the work

```
planlint --target . detect                    # what this repo actually does
planlint --target . validate --fail-on ERROR  # the gate
```

Run `detect` first. It reports the dialect, the coverage-threshold locator,
and the make targets it found, which is the context every finding is phrased
against. For structured output use `validate --json` for findings, and
`detect --format json` for a portable, schema-versioned dialect card --
`detect --json` is a legacy shape carrying machine-specific absolute paths.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | No findings at or above the threshold | Report the pass. |
| 1 | Findings at or above `--fail-on` | List them verbatim. This is a real failure. |
| 2 | Precondition or usage error | Not a spec failure. See below. |

Exit 2 is the one most likely to be misread. It means the command could not
run, not that the specs are bad. The three cases you will actually hit:

- **No spec tree.** `validate` and `waivers` print `no openspec/ directory and
  no SpecKit specs/ tree; run ``planlint init`` first`. `graph` prints a longer
  form naming both absolute paths. In all three cases the correct report is
  "planlint does not apply to this repository yet". You may offer
  `planlint init --dry-run` to show what scaffolding would be created. Run
  `init` itself only if the user asks for it.
- **Unknown change package.** `no specs found for change 'name'` means the
  `--change` value does not match a directory. Check the name; do not scaffold.
- **Bad target path.** A `--target` that is not a directory exits 2 with
  `ERROR target is not a directory: <path>`.

A nonzero exit is never overridden by your own reading of the spec. If you
believe a rule has misfired, say so, quote the finding, and leave the run
failed. Do not report a pass that the tool did not report.

## Verbs, and which ones write

Read-only. Safe to run at any time, on any repository:

| Verb | Purpose |
|---|---|
| `detect` | Stack, dialect, threshold locator, make targets |
| `validate` | The rule engine; the gate |
| `graph` | Spec dependency graph, as JSON or Mermaid |
| `rules` | The rule table this build carries |
| `waivers` | Every waived rule across the tree |

Writes files. Do not run these unless the user asks:

| Verb | Writes |
|---|---|
| `init` | Two files: a config snapshot and a project document under `openspec/` |
| `new` | Three files: a proposal, tasks, and a spec for one change package |
| `witness` | One record under the target's own hidden witness store |

`init` and `new` both accept `--dry-run`, which prints the plan and writes
nothing. Prefer it. Neither overwrites an existing file unless `--force` is
passed. **Never pass `--force`.**

`new --dialect` accepts only the harness and upstream dialects. A repository
using the SpecKit dialect can be validated but not scaffolded; say so rather
than producing a package in the wrong shape.

## Repairing a failing spec

You may edit an existing spec to resolve a finding, then re-run `validate` and
report the new exit code. That is the intended loop.

You must not make a finding disappear without changing the fact behind it.
Specifically, never:

- Add a waiver comment. A waiver is a claim that must justify itself, the
  reason text is the user's to write, and the engine rejects a reason-less
  waiver anyway. If a waiver is genuinely right, propose it and let the user
  approve the wording.
- Run `witness`. A witness records that continuous integration really ran a
  stage. Recording one yourself asserts something you did not observe.
- Edit the coverage floor, or any threshold the spec is measured against.
- Rename or add a Makefile target so that a citation resolves. Fix the
  citation in the spec instead.
- Delete a spec, or regenerate one over the top of an existing file.
- Write spec prose from nothing. This tool evaluates plans; it does not author
  them.

## Witness mode

The witness rules are not evaluated by a plain `validate` run. They apply only
when `--require-witness` is passed, and their absence from a normal run is by
design, not a gap. Do not describe a passing `validate` as proof that any
stage actually executed.

## What it does to the repository

Nothing, for the read-only verbs above. `planlint` never runs `make` and never
evaluates the target repository's own file contents as code. It makes exactly
one subprocess call, a read-only `git rev-parse HEAD`, used to check whether a
recorded witness matches the current commit; every failure of that call is
treated as "unknown" rather than as an error.

## Wiring it into CI

`assets/spec-gate.yml` is a ready workflow: it runs `detect` so drift shows up
in the log even on a pass, then `validate` as the blocking gate. Copy it into
the target repository's own workflows directory.

## References

- `references/rule-catalog.md` -- every rule id, severity, dialect and summary.
- `references/exit-codes.md` -- the full per-verb exit-code contract.
- `references/dialects.md` -- the three dialects and how they are detected.
