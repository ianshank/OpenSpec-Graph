# Milestones

## Milestone 1 — Force UTF-8 on stdout and stderr at the CLI entry point [DONE]

- `openspec_graph/cli.py`: `main()` reconfigures both `sys.stdout` and
  `sys.stderr` to UTF-8 before parsing args (DEC-SE-002), wrapped in
  `try/except (ValueError, OSError)` so an already-closed or
  non-reconfigurable stream degrades gracefully instead of crashing
  (DEC-SE-004).
- `tests/support.py`: `run_cli()` decodes subprocess output as UTF-8
  explicitly (matching the child's now-deterministic encoding);
  `write_spec()` writes fixture content as UTF-8 explicitly (needed to
  construct a non-ASCII fixture at all).
- `tests/test_cli_surface.py`: 5 new tests — the hardcoded-literal crash
  across `detect`/`init`/`new`/`validate` (pass and fail), arbitrary
  non-ASCII spec content through `graph --format mermaid`, a non-ASCII
  `--target` path on stderr (DEC-SE-003), JSON-output parity, and a
  reconfigure-raises double (parametrized over `ValueError`/`OSError` —
  the two exception types the guard's `except` clause actually names,
  after an initial version only exercised `OSError` despite its own
  docstring describing the `ValueError` case) proving `main()` tolerates
  a stream that cannot be reconfigured (R-SE-3, DEC-SE-004).
- **Gate:** `make test` green.

## Milestone 2 — Confirm no regression on the already-safe paths [DONE]

- Full suite re-run: confirms this fix is a no-op on a platform whose
  ambient encoding was already UTF-8-compatible, and that no other test
  depended on the old, unconfigured stdout/stderr encoding.
- **Gate:** `make pre-pr` green; `planlint validate` clean.
