# Spec: Spec Read Errors

> **Change:** `fix-unreadable-spec-exit-code`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`parse.parse_spec` reads a discovered spec with a bare
`path.read_text(encoding="utf-8", errors="replace")` and no guard. Three
callers invoke it unguarded — `cli.cmd_validate`, `cli.cmd_waivers`, and
`graph.build_graph`, whose parse loop walks the whole tree before any output
is produced — so a spec path that exists but cannot be read raises an
uncaught `OSError`, printing a traceback and exiting **1**. Exit 1 is
reserved by the documented contract for "findings at or above the fail
level"; a broken mount, a permission-denied checkout, or a path of the wrong
file type is exit 2, "the command could not run."

**Evidence:** reproduced directly — a directory named `spec.md` at
`openspec/changes/<name>/specs/<cap>/spec.md`, a shape
`detect.find_spec_files`' `changes/*/specs/*/spec.md` glob yields because
glob matches names rather than readability, produces an `IsADirectoryError`
traceback and exit 1 from `validate`, `validate --json`, `waivers`, and
`graph --format json` alike. `detect.py` already handles this class
correctly at every one of its own reads (`_threshold`, `_invariants`,
`_adrs`, `detect_dialect`, `find_speckit_spec_files`, each with an `except
OSError` and a `logger.debug` naming the path), and
`tests/test_detect_speckit.py::test_find_speckit_spec_files_skips_an_unreadable_candidate_not_crashes`
already builds its fixture as a directory named `spec.md` for exactly this
reason. The parse layer is the single read path never given that treatment,
and it is the one every CI-run verb goes through. Same defect class as
`DEC-SD-001` (`init`/`new` on an unwritable target), one verb further in:
that change fixed the write boundary and left the read boundary untouched.

A second defect shares the code path: on a SpecKit-only target,
`validate --change <name>` exits 2 with `no specs found for change 'name'`,
which reads as "your package is missing" when the real answer is that
`--change` selects an OpenSpec change package and has no SpecKit equivalent
today — a limitation `DEC-SK-006` records in the design but no message ever
states to the operator.

---

## Requirements

- R-RE-1: A discovered spec path that exists but whose bytes cannot be read
  MUST NOT let an `OSError` escape any CLI verb. `validate` (text and
  `--json`), `waivers` (text and `--format json`), and `graph` (`--format
  json` and `--format mermaid`) MUST each terminate with a single-line
  message on stderr and no traceback.
- R-RE-2: That termination MUST be exit **2**, never 0 and never 1. Exit 1
  stays reserved for findings at or above `--fail-on`, exactly as
  `skills/planlint-spec-governance/references/exit-codes.md` states.
- R-RE-3: The message MUST name the offending spec path **root-relative**
  (rendered through `detect.to_posix_relative`, so it is forward-slash on
  every host OS per `R-PS-1`/`R-PS-2`) and MUST name the underlying reason
  the read failed.
- R-RE-4: The `OSError` MUST be translated into a typed exception carrying
  the path and the reason, raised at the one place spec bytes are read
  (`parse.parse_spec`), and chained from the original (`raise ... from
  exc`). No caller MUST depend on catching `OSError` itself. The exception's
  own `str()` MUST stay terse (`"{path}: {reason}"`, the absolute path) and
  MUST NOT restate the operator-facing wording, which lives once in
  `cli._UNREADABLE_SPEC`.
- R-RE-5: `graph.build_graph` MUST propagate that exception rather than
  catching it, and MUST NOT own an exit code; `cmd_graph` MUST catch it
  alongside the existing `NoOpenSpecTreeError` handling. `graph.py` MUST NOT
  import `cli`.
- R-RE-6: Each operator-facing message template this change introduces or
  edits — the unreadable-spec line, and the pair of `--change`-found-nothing
  lines — MUST exist exactly once as a named module constant in `cli.py`,
  and MUST reach stderr through exactly one shared helper rather than
  through per-verb call sites: `cli._report_unreadable` for the first,
  `cli._report_no_specs_for_change` for the second (which also owns the
  choice between the two templates). No verb MUST restate any of the
  literals, re-implement the template selection, or carry its own copy of
  the exit code.
- R-RE-7: `validate --change <name>` against a target that has a SpecKit
  `specs/` tree and no `openspec/` tree MUST exit 2 with a message that says
  plainly that `--change` scopes OpenSpec change packages and does not apply
  to a SpecKit tree, and MUST name the re-run without `--change` as the way
  forward.
- R-RE-8: The read failure MUST be recorded at `logger.debug` in both
  places it is observable — where the `OSError` is translated, and where a
  verb aborts on it — consistent with `detect.py`'s diagnostic logging
  style, which names the path and the underlying error in every such record.
- R-RE-9: The typed exception MUST be importable from the package root
  (`from openspec_graph import SpecReadError`), beside `NoOpenSpecTreeError`,
  and `build_graph`'s docstring MUST record that it propagates.
- R-RE-10: The new exit-2 case MUST be documented in
  `skills/planlint-spec-governance/references/exit-codes.md`, whose message
  quotes `tests/test_skill_contract.py` pins, so an agent reading the skill
  is told the same thing the CLI prints.
- C-RE-1: This change MUST NOT alter what exit 1 means. A spec that parses
  and then fails rules MUST still exit 1 and MUST still list its findings; a
  clean tree MUST still exit 0. The new guard MUST NOT convert any finding
  into a precondition failure.
- C-RE-2: An unreadable spec MUST NOT be silently skipped by an **unscoped**
  run. `validate` invoked without `--change` MUST NOT report `PASS` (or a
  reduced `N spec(s) checked` count) for a tree in which a discovered spec
  could not be read. A `--change`-scoped run parses only the packages the
  filter selected and makes no claim about specs outside that scope, so it
  is deliberately outside this constraint — `DEC-RE-009` records the
  asymmetry and why it is correct.
- C-RE-3: `detect.py`'s own OSError handling MUST NOT change. Its reads stay
  skip-and-continue; only the parse layer fails closed.
- C-RE-4: An OpenSpec target's existing `no specs found for change 'name'`
  message MUST stay byte-identical, on both `validate` and `graph`.

---

## Decisions

- **DEC-RE-001:** the failure exits 2, not 1. The alternative — documenting
  the traceback-and-exit-1 behaviour as-is — was rejected for the reason
  `DEC-SD-001` already gave for `init`/`new`: the skill's single most
  load-bearing sentence is that exit 1 means findings, and an exit 1 carrying
  no findings at all (indeed, carrying a traceback) makes that sentence false
  in the situation a CI job hits when a mount, a permission bit, or a
  checkout goes wrong. `witness` and the two write verbs already validate
  their boundaries at exit 2; this aligns the read boundary with them rather
  than inventing a convention.
- **DEC-RE-002:** the `OSError` is translated at the read itself, inside
  `parse_spec`, into a typed `SpecReadError` — not returned as a sentinel,
  and not caught separately at each of the three call sites. A sentinel
  return value (a `ParsedSpec` with an error flag, or `None`) would make
  `parse_spec` non-total in its declared return type and would push a check
  onto every present and future caller, so the defect returns the first time
  someone forgets one — the same shape as the current bug. Catching
  `OSError` at each call site leaves `parse_spec` itself unguarded, so the
  next caller inherits the defect for free. Translating at the read keeps
  exactly one guard, gives every caller one typed thing to catch, and never
  yields a half-parsed document. Note this is a deliberate refinement of the
  original design brief's "do not catch inside `parse_spec`": that
  instruction was aimed at *swallowing* the error (which does require a
  sentinel); raising a typed error instead swallows nothing and needs no
  sentinel at all.
- **DEC-RE-003:** `SpecReadError` lives in `parse.py`, not in `graph.py`
  beside `NoOpenSpecTreeError` and not in a new `errors.py`. `parse.py` is
  strictly below both `cli.py` and `graph.py`, and both already import it
  (`from .parse import ParsedSpec, parse_spec`; `from . import detect, parse,
  rules`), so the definition needs no new import edge anywhere and cannot
  tempt `graph.py` into importing `cli` — a boundary
  `tests/test_decomposition.py::test_import_boundary_discipline` enforces.
  Placing it beside `NoOpenSpecTreeError` was considered, since that is the
  package's one existing typed CLI-facing error and the pattern is proven:
  rejected because `cmd_validate` and `cmd_waivers` never build a graph, and
  making them catch a graph-layer exception would couple two verbs to a
  module they have no other reason to touch. A dedicated `errors.py` was
  rejected as a module for a single class, against this codebase's
  on-the-record precedent (`DEC-AD-003`) about genericizing two-to-three
  instance special cases.
- **DEC-RE-004:** the parse layer fails **closed** (abort the run) while
  `detect.py` fails **open** (skip the file and continue), and that asymmetry
  is deliberate, not an inconsistency to unify later. `detect.py` reads
  *optional* inputs: a maybe-present `CONTRACT.md`, one ADR file among
  several candidates, a per-file dialect vote — losing one degrades a hint.
  A discovered spec is a *mandatory* input: skipping it would let a
  permission-denied spec pass a gate that never read it, which is a worse
  outcome than any crash, because it is silent and green.
- **DEC-RE-005:** the rendered `reason` comes from `OSError.strerror`, with
  `str(exc)` as the fallback. `strerror` is the short, stable, localized
  kernel reason ("Is a directory", "Permission denied") and excludes the
  absolute filename `str(exc)` would repeat — the message already names the
  path once, root-relative, and printing an absolute copy beside it is the
  noise `DEC-PS-002` avoids elsewhere. `strerror` is `None` for some
  `OSError` subclasses raised without an errno, so the fallback is explicit
  rather than assumed.
- **DEC-RE-006:** every operator-facing string this change touches is
  single-sourced by a **helper**, not by call-site discipline — the wording,
  the relativization, the debug record, the template selection, and the exit
  code all live in one function per message. `cli._report_unreadable(exc,
  root)` serves all three parsing verbs; `cli._report_no_specs_for_change(prof,
  change)` serves both verbs that accept `--change` and owns the
  `_NO_SPECS_FOR_CHANGE`-versus-`_CHANGE_IS_OPENSPEC_ONLY` choice, so the
  SpecKit gating condition exists once rather than in `cmd_validate` and
  `cmd_graph` separately. Two copies of a string an external consumer parses
  is the exact drift `_NOT_A_DIRECTORY`'s own comment says this repo has
  already paid for; two copies of a *selection rule* is worse, because the
  copies can agree on the wording and still disagree on when to print it.
  The same discipline is why `SpecReadError.__str__` stays terse
  (`"{path}: {reason}"`, absolute): a second, prettier rendering inside the
  exception would be a second copy of the operator wording that no test
  compares against the first, and the Agent Skill's exit-code reference
  quotes only the CLI's. The exit code lives in `cli.py`, never in
  `parse.py` or `graph.py`: those layers report facts, the CLI decides what a
  fact costs.
- **DEC-RE-007:** the SpecKit `--change` wording is a *second* constant
  (`_CHANGE_IS_OPENSPEC_ONLY`) selected by a `prof.speckit_root and not
  prof.openspec_root` condition, rather than a replacement for the existing
  message. `tests/test_skill_contract.py` asserts the OpenSpec message with
  `==` on the whole stderr line, and `exit-codes.md` and `SKILL.md` both
  quote it verbatim; changing it for every target would break three pinned
  consumers to fix one target shape. Gating on "SpecKit tree present *and*
  no OpenSpec tree" is what makes the claim in the new message true — a
  mixed repo really does have change packages, and really should get the
  original "no such package" answer.
- **DEC-RE-008:** no dangling-symlink diagnostic is added here, even though a
  broken link is one way to reach this guard. Its `ENOENT` reason already
  renders through the same one-line message; distinguishing "the link target
  is gone" from "the path is the wrong type" needs discovery-layer knowledge
  (`detect.find_spec_files`) this change deliberately does not touch, and
  de-duplicating a spec reachable through two paths belongs to the separate
  symlink-dedup change that owns that layer. Splitting it out keeps this
  change's blast radius at "translate one error, exit one code."
- **DEC-RE-009 (found by adversarial review after implementation):** a
  `--change`-scoped run and an unscoped run answer an unreadable spec
  **differently**, and the difference is correct rather than a hole in
  `C-RE-2`. Measured against a target holding a readable, passing
  `openspec/changes/good/specs/cap/spec.md` and a directory named `spec.md`
  at `openspec/changes/broken/specs/cap/spec.md`: `validate --change good`
  exits 0 and prints `PASS`, because `detect.filter_by_change` narrows
  `spec_files` before the parse loop and the unreadable path is never opened;
  `graph --change good --format json` exits 2 with the unreadable-spec line,
  because `build_graph` parses the whole tree regardless of the rendered
  scope. Neither prints a traceback. Both answers follow from contracts this
  repo already made. A `--change` run's contract is "does this one package
  pass": it already skips the tree-wide G006 and G009 checks outright with an
  `INFO` note (`DEC-WL-003`, `DEC-AD-004`) precisely because a tree-wide
  check breaks the locality the flag exists to provide — so it also cannot
  honestly claim anything about a spec outside the scope it was asked about,
  and reporting `PASS` for the one package it *did* read is the true answer
  to the question asked. `graph --change` is the opposite by design: its
  orphan check is deliberately unscoped (`DEC-GV-001`), it runs
  `evaluate_tree()` over the whole tree and folds the result into
  `broken_links` (`DEC-GV-002`), and it already prints two `INFO` lines
  warning that results may come from outside the rendered scope — a tree it
  must parse in full is a tree whose unreadable spec it must fail on.
  Narrowing `C-RE-2` to unscoped runs records this rather than papering over
  it; widening the guard instead (making `validate --change` stat every spec
  in the tree) was rejected because it would give the flag a tree-wide
  failure mode after `DEC-WL-003` deliberately removed its tree-wide checks,
  and would make a `--change` run fail on a package the operator did not ask
  about. **No automated test covers this pair yet**; the behaviour above is a
  manual reproduction, recorded here and cited by `AC-RE-12` the way this
  repo already cites non-automated checks elsewhere — a `manual … · stage:`
  selector, as in `fix-subprocess-coverage-blind-spot` and
  `fix-adopter-artifact-drift` — rather than naming a test that does not
  exist. A regression test belongs with whichever change next touches
  `--change` scoping.

---

## Acceptance Criteria

- [x] **AC-RE-1:** An unreadable spec (a directory named `spec.md` under a
  change package) yields exit **2** from `validate`, `validate --json`,
  `waivers`, `waivers --format json`, `graph --format json`, and `graph
  --format mermaid` — never 0, never 1 — and stderr carries exactly one
  line, with no `Traceback (most recent call last)` for any of them.
  (R-RE-1, R-RE-2, R-RE-5)
  _Verified by:_ `pytest -k "test_unreadable_spec_exits_2_from_every_parsing_verb or test_unreadable_spec_never_prints_a_traceback"` · stage: `make test`

- [x] **AC-RE-2:** That message names the offending path root-relative and
  forward-slash rendered (never the absolute path, never a backslash), and
  names the underlying reason; a consumer piping stdout receives nothing it
  could misread as a clean result. (R-RE-3, DEC-RE-005)
  _Verified by:_ `pytest -k "test_message_names_the_path_root_relative_and_the_reason or test_json_output_is_not_emitted_alongside_the_error"` · stage: `make test`

- [x] **AC-RE-3:** `parse.parse_spec` raises `SpecReadError` — carrying
  `path` and `reason`, chained from the original `OSError` via
  `__cause__`, and rendering the terse `"{path}: {reason}"` rather than the
  operator wording — for an unreadable path, while a readable path still
  parses unchanged; and that class is importable both as
  `openspec_graph.parse.SpecReadError` and from the package root. (R-RE-4,
  R-RE-9, DEC-RE-002, DEC-RE-003)
  _Verified by:_ `pytest -k "test_spec_read_error_carries_path_and_reason or test_spec_read_error_chains_the_original_oserror or test_a_readable_spec_still_parses or test_public_import_compatibility"` · stage: `make test`

- [x] **AC-RE-4 (non-success):** the guard does not convert real findings
  into precondition failures — a spec that parses and violates a rule still
  exits **1** with its findings listed, and a clean tree still exits **0**
  with `PASS`, both with the guard in place. (C-RE-1)
  _Verified by:_ `pytest -k "test_a_spec_with_real_findings_still_exits_1 or test_a_clean_tree_still_exits_0"` · stage: `make test`

- [x] **AC-RE-5 (non-success):** an unreadable spec is never silently
  skipped by an unscoped run: `validate` against a tree containing one
  readable, passing spec and one unreadable spec does **not** print `PASS`
  and exits 2 — the fail-closed behaviour that separates the parse layer
  from `detect.py`'s fail-open reads. (C-RE-2, DEC-RE-004)
  _Verified by:_ `pytest -k test_one_unreadable_spec_does_not_let_the_others_pass_silently` · stage: `make test`

- [x] **AC-RE-6:** `graph.build_graph` propagates `SpecReadError` to its
  caller rather than catching it or emitting a partial graph — both `graph`
  formats exit 2 on an unreadable spec while a fully readable tree still
  renders a valid graph and exits 0 — and `graph.py` still imports neither
  `cli` nor anything above it. (R-RE-5, R-RE-9)
  _Verified by:_ `pytest -k "test_unreadable_spec_exits_2_from_every_parsing_verb or test_graph_json_stays_valid_when_every_spec_is_readable or test_import_boundary_discipline"` · stage: `make test`

- [x] **AC-RE-7:** `validate --change <name>` on a SpecKit-only target exits
  2 with a message naming `--change` as OpenSpec-only and pointing at the
  unscoped re-run. (R-RE-7, DEC-RE-007)
  _Verified by:_ `pytest -k test_change_on_a_speckit_only_target_names_the_limitation` · stage: `make test`

- [x] **AC-RE-8 (non-success):** an OpenSpec target's unknown-`--change`
  stderr line is unchanged, byte for byte, on both `validate` and `graph`,
  and carries no mention of SpecKit — the new wording fires only for a
  SpecKit-only target. (C-RE-4, DEC-RE-007)
  _Verified by:_ `pytest -k "test_change_on_an_openspec_target_keeps_the_original_message or test_unknown_change_package_exits_two or test_graph_unknown_change_exits_two"` · stage: `make test`

- [x] **AC-RE-9:** the two exit-2 paths stay distinguishable and stay
  single-sourced: an absent tree still produces its own `planlint init`
  message rather than the read-error one, the documented wording in
  `references/exit-codes.md` matches what the CLI prints, and each literal
  reaches stderr through exactly one helper. (R-RE-6, R-RE-10, DEC-RE-006)
  _Verified by:_ `pytest -k "test_graph_still_reports_a_missing_tree_distinctly or test_exit_two_messages_match_the_documented_contract"` · stage: `make test`, plus manual review that `_UNREADABLE_SPEC`, `_NO_SPECS_FOR_CHANGE` and `_CHANGE_IS_OPENSPEC_ONLY` each appear once under `openspec_graph/` — no automated single-sourcing check exists

- [x] **AC-RE-10:** the translation and the abort are both observable at
  `logger.debug` — the translation record names the path and the OS error,
  and the abort record names the path and the reason — matching `detect.py`'s
  diagnostic style. (R-RE-8)
  _Verified by:_ manual code review of `parse.parse_spec` and `cli._report_unreadable`; no `caplog` test exists in this suite · stage: `make test`

- [x] **AC-RE-11 (non-success):** `detect.py`'s fail-open reads are
  unchanged: an unreadable ADR candidate, invariant candidate, or SpecKit
  dialect-vote candidate is still skipped with the run continuing, not
  escalated to exit 2. (C-RE-3, DEC-RE-004)
  _Verified by:_ `pytest -k "test_detect_dialect_skips_an_unreadable_spec_path_not_crashes or test_find_speckit_spec_files_skips_an_unreadable_candidate_not_crashes"` · stage: `make test`

- [x] **AC-RE-12 (non-success):** a `--change`-scoped run makes no claim
  about a spec outside its scope, and the two verbs that accept the flag
  therefore differ. Against a target with a readable, passing
  `changes/good` and an unreadable `changes/broken/specs/cap/spec.md`:
  `validate --change good` exits **0** and prints `PASS` (it parses only the
  filtered set); `graph --change good --format json` exits **2** with the
  unreadable-spec line (`build_graph` parses the whole tree for its unscoped
  orphan check). Neither prints a traceback, and the unscoped forms of both
  still exit 2. (C-RE-2, DEC-RE-009)
  _Verified by:_ manual reproduction recorded in `DEC-RE-009`; no automated test covers this pair yet · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-RE-1..12 (AC-RE-10 and AC-RE-12 by the manual checks their selectors name) |
| Self-check | `make validate` | this repo's own change packages stay clean with the guard in place |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
