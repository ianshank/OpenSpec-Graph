# PLAN.md — planlint E2E test run & defect triage

## Goal
Clone `ianshank/planlint`, create a working branch, run the e2e test suite in
two modes ("with mocks" / "without mocks"), and triage + root-cause every
defect discovered. No fixes requested — investigation + reporting only.

## Repo shape (discovered)
- Pure-Python CLI: package `openspec_graph`, entry point `planlint` (+ deprecated
  alias `specgraph`). Zero runtime dependencies. Requires Python >=3.10.
- Dev deps: pytest, pytest-cov, ruff, mypy, tomli (py<3.11).
- Test suite (`tests/`): pytest fixtures + `tests/support.py::run_cli()`, which
  spawns the real CLI as a subprocess against temp repos (already e2e-style),
  plus ~21 `monkeypatch` call sites across 6 files simulating edge conditions
  (no git, corrupt witness files, unwritable dirs, missing subprocess, etc.)
- CI (`.github/workflows/ci.yml`) has 5 jobs: `test` (make test), `self-validate`
  (runs the real built CLI live against this repo: detect/validate/graph),
  `graph-diff`, `security` (gitleaks + hardcoded-threshold check), `docs`.
- No `make` binary on this Windows/Git-Bash box — running the Makefile's
  underlying commands directly (contents already read from `Makefile`).
- No `.claude/` harness dir inside planlint itself — the CLAUDE.md harness
  config being followed this session lives one level up (`E:\Coding_Projects\.claude\`)
  and applies across projects; not part of planlint's own repo.

## Interpretation of "e2e w/ and w/o mocks" for *this* repo
There's no built-in `test:mock` / `test:live` npm-style split here (it's a
Python CLI linter, not a web app with network mocking). Mapping onto this
repo's own existing dual-track design instead:
- **WITH MOCKS** = the pytest suite (`make test` equivalent): fixture repos +
  `monkeypatch`-simulated edge cases + real-subprocess CLI calls.
- **WITHOUT MOCKS** = live self-validation: the actual installed `planlint`
  binary run against this real, live repo with zero monkeypatching/fixtures —
  mirrors CI's dedicated `self-validate` job exactly (`detect`, `validate
  --fail-on ERROR`, `graph --format json`, `validate --fail-on WARN --json`).
- Supplementary hard gates (lint, typecheck, security, docs-check, thresholds)
  also run since they're this repo's own definition of done and any failures
  are real, reportable defects — kept clearly separated from the two "e2e"
  runs above in the final report.

## Steps
1. [x] Clone repo, explore structure/tests/CI to ground the plan above
2. [x] Create branch `test/e2e-mock-and-live-triage`
3. [x] venv + `pip install -e ".[dev]"`
4. [x] Run WITH-MOCKS: pytest suite w/ coverage gates — capture full output
   (343 passed, 11 failed; line cov 98.3%/floor 90%, branch cov 97.9%/floor 80%)
5. [x] Run WITHOUT-MOCKS: live self-validate flow — capture full output
   (all 4 steps exit 0, 0 errors/warnings; deeper probe found Defect D)
6. [x] Run supplementary gates: lint, typecheck, security, docs-check, thresholds
   (all 5 pass clean)
7. [x] Enumerate every failure/defect from steps 4-6 (11 pytest failures +
   1 additional live-track defect found by varying encoding env)
8. [x] Per defect: triage (severity/category) + RCA (root cause, evidence,
   file:line) — grouped into 4 root causes (A-D), written up in NOTES.md
9. [x] Write findings to `NOTES.md` in this repo
10. [x] Final report per CLAUDE.md format + Stop-hook checklist

## Verification
- Tests run and pass/fail counts will be reported verbatim from tool output,
  not summarized from memory.
- No fixes are in scope; defects are reported, not patched, unless the user
  asks for fixes after seeing the triage.

---

# Implementation Plan — fixing the 4 defects

User approved an implementation plan (full text: `C:\Users\iansh\.claude\plans\please-create-plan-to-radiant-hickey.md`,
written via plan mode after two independent adversarial reviews). Condensed
build order below; see that file for full reasoning/decisions.

**Delivery split:** Unit 1 (Defect D, small/high-severity) ships first;
Unit 2 (Defect A, larger refactor) ships second. B/C are independent
test-only guards. CI Windows leg: **recommended against for now** (revised
after review found zero evidence of real Windows users — one-day-old,
solo-maintainer project) — not implementing unless asked.

## Steps
1. [ ] Unit 1 — Defect D: `main()` stdout/stderr UTF-8 fix in `cli.py`
       (try/except around `.reconfigure()`, not just `hasattr`)
2. [ ] Unit 1 — new tests in `tests/test_cli_surface.py` (ascii-encoding
       crash repro x4 verbs, non-ASCII spec content via mermaid, deterministic
       non-ASCII `--target` stderr case, json-output-unaffected check)
3. [ ] Unit 1 — `openspec/changes/fix-stdout-encoding-crash/` package
       (proposal.md/spec.md/tasks.md, small template, written after tests pass)
4. [ ] Unit 2 — add `to_posix_relative(path, root)` to `detect.py`
5. [ ] Unit 2 — migrate all 12 call sites (graph.py, ledger.py, rule_types.py,
       detect.py, scaffold.py, cli.py) — `Finding.as_dict()` and the cli.py
       sort key deliberately EXCLUDED
6. [ ] Unit 2 — update `test_graph_relative_to_outside_root_falls_back`;
       add `to_posix_relative` unit tests + `test_graft.py`/`test_cli_surface.py`
       additions (incl. `plan_init()` persistence test)
7. [ ] Unit 2 — `openspec/changes/fix-windows-path-separator-leak/` package
       (full template, written after tests pass)
8. [ ] Unit 2 — `planlint validate` against this repo (dogfood the new specs)
9. [ ] Workstream 3 — `supports_symlinks()` probe in `tests/support.py` +
       skipif guards (test_witness.py, test_graft.py) + make-missing skipif
       (test_enterprise.py)
10. [ ] CHANGELOG.md entries for both units (incl. `init --force` migration
        note and the `as_dict()` compatibility caveat)
11. [ ] Full verification pass (see below) + final report

## Verification (for this implementation phase)
- Full pytest suite: previously-11-failing tests now pass, 2 B/C tests skip
  (not fail) on this box, new tests pass, coverage floors (90%/80%) hold.
- `PYTHONIOENCODING=ascii planlint --target . validate --fail-on ERROR` exits 0.
- Live self-validate (detect/validate/graph) — 0 errors, including the 2 new
  change packages.
- `ruff check` / `mypy` / `check_secrets.py` / `check_docs.py` /
  `check_no_hardcoded_thresholds.py` all stay clean.
- Manual smoke check: `planlint init` with a nested invariant source — confirm
  forward slashes in `specgraph.json`/`project.md`.
