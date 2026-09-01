# Change: Fix Stdout Encoding Crash

## Why

`cli.py`'s `print()` calls depend on the ambient `sys.stdout`/`sys.stderr`
encoding, with no explicit configuration anywhere in the package. Two
hardcoded non-ASCII characters already live in the CLI's own output — `·`
(U+00B7 MIDDLE DOT, `cmd_validate`'s summary line) and `—` (U+2014 EM DASH,
`cmd_detect`/`cmd_init`/`cmd_new`/`cmd_validate`) — and `graph --format
mermaid` additionally echoes arbitrary, unbounded non-ASCII text straight
from a spec's own requirement/criterion prose.

**Evidence:** reproduced directly — `PYTHONIOENCODING=ascii planlint
--target . validate --fail-on ERROR` raised `UnicodeEncodeError: 'ascii'
codec can't encode character '\xb7' in position 21: ordinal not in
range(128)` from `cmd_validate`'s summary print, exit code 1 —
indistinguishable at the exit-code level from "found real errors," but
actually an unhandled crash on the tool's single most common command,
under a realistic environment: plain ASCII, a `LANG=C` locale, or a
Windows console codepage lacking the glyph. Every file read/write
elsewhere in the package already passes `encoding="utf-8"` explicitly
(`parse.py`, `detect.py`, `scaffold.py`); stdout/stderr printing was the
one place never considered, plausibly because the project's only tested
environment (Ubuntu CI) never triggers the gap — CPython's PEP 538
auto-coerces a `C`/`POSIX` locale to `C.UTF-8` there.

## What Changes

- `cli.py`'s `main()` — the single entry point every path funnels through
  (the console script, `python -m openspec_graph.cli`, and the deprecated
  `specgraph` alias via `main_deprecated`): reconfigures both `sys.stdout`
  and `sys.stderr` to UTF-8 before `build_parser().parse_args(argv)` runs,
  ahead of every subcommand.
- Guarded against both a stream with no `reconfigure` attribute and one
  whose `reconfigure()` itself raises (e.g. an already-closed stream) —
  `main()` falls back to the ambient encoding rather than crashing before
  any subcommand has a chance to run.
- `tests/support.py`'s `run_cli`/`write_spec` helpers also given explicit
  UTF-8 encoding — needed to actually construct and decode non-ASCII spec
  content in tests at all; both previously assumed the platform-default
  encoding.
- No change to the CLI's hardcoded non-ASCII characters themselves; they
  stay exactly as written. No change to JSON output.

## Non-Goals

- No replacement of the hardcoded middle dot / em dash with ASCII
  equivalents — that would only fix today's one known reproduction, not
  the open-ended case where arbitrary non-ASCII spec content flows into
  `graph --format mermaid` or a rule message.
- No new environment-variable guidance (`PYTHONUTF8`, `PYTHONIOENCODING`)
  for adopters — the fix makes the tool correct by construction, with no
  caller-side action required.

## Affected Capabilities

- `stdout-encoding`
