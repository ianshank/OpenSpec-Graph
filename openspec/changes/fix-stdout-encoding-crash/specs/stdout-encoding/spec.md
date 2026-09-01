# Spec: Stdout Encoding

> **Change:** `fix-stdout-encoding-crash`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`cli.py`'s `print()` calls depend on the ambient `sys.stdout`/`sys.stderr`
encoding, with no explicit configuration anywhere in the package. Two
hardcoded non-ASCII characters already live in the CLI's own output — `·`
(U+00B7 MIDDLE DOT) and `—` (U+2014 EM DASH) — and `graph --format
mermaid` additionally echoes arbitrary, unbounded non-ASCII text straight
from a spec's own requirement/criterion prose.

**Evidence:** reproduced directly — `PYTHONIOENCODING=ascii planlint
--target . validate --fail-on ERROR` raised `UnicodeEncodeError: 'ascii'
codec can't encode character '\xb7' in position 21: ordinal not in
range(128)` from `cmd_validate`'s summary print, exit code 1 — an
unhandled crash on the tool's single most common command, under a
realistic (not contrived) environment.

---

## Requirements

- R-SE-1: `planlint`'s CLI entry point (`main()` in `cli.py`) MUST
  configure both stdout and stderr to encode as UTF-8 before any
  subcommand runs, so that printing any Unicode content never raises
  `UnicodeEncodeError`, regardless of the ambient `PYTHONIOENCODING`,
  locale, or console codepage.
- R-SE-2: The fix MUST cover arbitrary non-ASCII content read from a
  user's own spec files and echoed back — `graph --format mermaid`'s node
  labels — not only the CLI's own hardcoded characters, and not only
  stdout: a non-ASCII value embedded in a stderr error message (e.g. an
  absolute target path) MUST survive equally.
- R-SE-3: Reconfiguring stdout/stderr's encoding MUST NOT raise if a
  stream does not support it, or is already closed — `main()` MUST fall
  back to leaving the ambient encoding in place rather than crashing
  before any subcommand has a chance to run.
- C-SE-1: Forcing UTF-8 MUST NOT change any character actually emitted on
  a platform whose ambient encoding was already UTF-8-compatible — every
  existing byte-identical golden-output test stays unaffected.
- C-SE-2: Every `--json`/`--format json` output path is unaffected:
  `json.dumps(..., ensure_ascii=True)`'s default already escapes every
  non-ASCII code point, so it never depended on the ambient stdout
  encoding.

---

## Decisions

- **DEC-SE-001:** fix by reconfiguring stdout/stderr's *encoding* to
  UTF-8, not by replacing the CLI's own `·`/`—` with ASCII equivalents.
  Character substitution would only fix today's one known reproduction —
  it cannot fix `graph --format mermaid` echoing arbitrary non-ASCII
  content from a user's own spec, which this tool does not own and must
  reproduce exactly, not sanitize. `errors="backslashreplace"` is kept on
  the *target* UTF-8 encoding purely as defense-in-depth (UTF-8 can
  represent every valid Python `str`, so this branch has no known trigger
  today).
- **DEC-SE-002:** the reconfiguration happens once, at the top of
  `main()`, before `build_parser().parse_args(argv)` runs — not inside
  each `cmd_*` handler. Every print in the package funnels through
  `cli.py`'s `cmd_*` functions, and both installed commands (`planlint`,
  the deprecated `specgraph` alias via `main_deprecated`) funnel through
  this one `main()`, so one call site covers every verb without needing
  to be repeated, or forgotten, when a future verb is added.
- **DEC-SE-003:** stderr is fixed alongside stdout. An earlier draft of
  this change scoped the fix to stdout only, reasoning that no stderr
  print *literal* contains non-ASCII text — that framing undercounts the
  real risk the same way the original bug did: several `file=sys.stderr`
  prints in `cli.py` embed *dynamic* content — an absolute target path
  (`_profile()`'s `"target is not a directory: ..."`, `cmd_witness`'s
  equivalent), a `--diff` baseline path — that can carry non-ASCII at
  runtime even though the source literal is plain ASCII. Confirmed
  directly: `PYTHONIOENCODING=ascii planlint --target <path with a
  non-ASCII component> detect` reproduces on stderr exactly as the
  stdout case did, with no real filesystem non-ASCII username needed —
  the target directory need not exist for this error path to fire.
- **DEC-SE-004:** each `.reconfigure()` call is wrapped in
  `try/except (ValueError, OSError)`, not guarded by
  `hasattr(stream, "reconfigure")` alone. Verified directly: calling
  `.reconfigure()` on an already-closed `TextIOWrapper` raises
  `ValueError`, a case `hasattr` does nothing to prevent — without the
  `try/except`, `main()` would crash unconditionally in that scenario, a
  failure mode that does not exist in the pre-fix code at all.

---

## Acceptance Criteria

- [x] **AC-SE-1:** `detect`, `init --dry-run`, `new --dry-run`, and
  `validate` (both a passing and a failing spec) all exit successfully
  under `PYTHONIOENCODING=ascii`, printing every hardcoded non-ASCII
  character without raising. (R-SE-1)
  _Verified by:_ `pytest -k test_common_verbs_do_not_crash_under_ascii_stdout_encoding` · stage: `make test`

- [x] **AC-SE-2:** `graph --format mermaid` against a spec whose
  requirement/criterion text contains arbitrary non-ASCII content exits 0
  under `PYTHONIOENCODING=ascii`, reproducing that content exactly rather
  than replacing or dropping it. (R-SE-2)
  _Verified by:_ `pytest -k test_arbitrary_non_ascii_spec_content_survives_graph_mermaid_under_ascii_encoding` · stage: `make test`

- [x] **AC-SE-3:** A non-ASCII `--target` path embedded in a stderr error
  message survives `PYTHONIOENCODING=ascii` without crashing, exactly as
  the stdout case does. (R-SE-2, DEC-SE-003)
  _Verified by:_ `pytest -k test_non_ascii_target_path_error_survives_ascii_stdout_encoding` · stage: `make test`

- [x] **AC-SE-4 (non-success):** `validate --json`'s output is
  byte-identical whether or not stdout's encoding was forced. (C-SE-2)
  _Verified by:_ `pytest -k test_json_output_is_unaffected_by_the_stdout_encoding_fix` · stage: `make test`

- [x] **AC-SE-5 (non-success):** the full existing test suite passes with
  this fix applied, confirming it changes nothing observable on the CI's
  Ubuntu runner, where the ambient encoding was already UTF-8-compatible.
  (C-SE-1)
  _Verified by:_ `make test` (full suite) · stage: `make test`

- [x] **AC-SE-6 (non-success):** `main()` does not crash, and the
  subcommand still completes and prints normally, even when reconfiguring
  stdout's encoding itself raises — covering both exception types the
  guard's `except` clause names (`ValueError`, matching a real
  already-closed `TextIOWrapper`'s verified behavior; `OSError`, a stream
  that simply doesn't support reconfiguration). (R-SE-3, DEC-SE-004)
  _Verified by:_ `pytest -k test_main_tolerates_a_stream_whose_reconfigure_raises` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-SE-1..5 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
