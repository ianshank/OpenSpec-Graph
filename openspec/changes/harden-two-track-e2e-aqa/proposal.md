# Change: Harden Two-Track E2E AQA

## Why

Three Windows-blind defects have shipped green through CI and were caught
only by manual runs on a Windows box:

1. `fix-windows-path-separator-leak` — eight tests hardcoded forward-slash
   paths and failed immediately on Windows; every CI job was
   `runs-on: ubuntu-latest`.
2. `fix-stdout-encoding-crash` — `planlint validate` raised
   `UnicodeEncodeError` under `PYTHONIOENCODING=ascii`; PEP 538 locale
   coercion on Linux masked it.
3. `tests/test_findings_envelope.py::test_two_checkout_paths_produce_identical_json`
   (added by `add-findings-json-envelope`) — normalizes the absolute
   `--target` out of JSON stdout with a raw-native-path `str.replace`,
   which can never match on Windows because `json.dumps` doubles every
   backslash. Failed the moment the suite ran on Windows; invisible on
   POSIX.

A fourth drift of the same kind, found by inspection during the same run:
`.github/workflows/ci.yml` gained a `packaging` job (via
`migrate-license-metadata-pep639`) that `docs/hooks.md`'s CI hooks table
never listed — no gate enforces the table ↔ workflow correspondence, so
the drift was silent.

Two structural gaps produce this pattern: (a) CI never executes on the OS
the platform-guard tests exist for, and never under the encoding the
encoding fix exists for; (b) the "no-mocks" live track — the installed CLI
run against this real repo, mirroring the `self-validate` job — exists
only inside CI YAML, not as one local command a contributor can run.

## What Changes

- **Makefile**: new `e2e-live` target composing the live verbs (`detect`,
  `validate --fail-on ERROR`, `graph --format json`, `waivers`) plus one
  `validate --fail-on ERROR` pass under `PYTHONIOENCODING=ascii` — the
  original crash environment. Added to `.PHONY` and `help`.
- **`.github/workflows/ci.yml`**: two new jobs —
  - `test-windows`: `windows-latest`, Git Bash shell, GNU make via
    Chocolatey (make is not preinstalled on the Windows runner image),
    then the same `make lint` / `make typecheck` / `make test` gates as
    the Ubuntu `test` job, on a single Python 3.12.
  - `encoding-stress`: `ubuntu-latest` with job-level
    `PYTHONIOENCODING=ascii` / `PYTHONUTF8=0`, running `make e2e-live`.
- **Guard tests** (`tests/test_ci_hardening.py`): the workflow must
  contain a Windows job and an encoding-stress job, the Makefile must
  define `e2e-live`, and every `jobs:` key in `ci.yml` must appear in
  `docs/hooks.md`'s CI table — the last one is the fence that would have
  caught the `packaging` drift.
- **Docs**: `docs/aqa.md` gains a "Two-track e2e" section defining the
  with-mocks / without-mocks split and how to reproduce it locally;
  `docs/hooks.md`'s CI table gains the `packaging` (backfill),
  `test-windows`, and `encoding-stress` rows; CHANGELOG entry.

## Non-Goals

- No full Windows Python-version matrix — the Ubuntu `test` matrix already
  covers version breadth (3.10–3.13); the Windows leg exists for platform
  breadth only (DEC-AQA-001).
- No pytest marker taxonomy (`e2e`/`live`/`mocked`) and no `conftest.py`
  split — the two tracks are defined by *how* they run (pytest fixtures +
  monkeypatch vs. the installed CLI against the live repo), not by
  selecting subsets of one suite.
- No macOS leg; no Docker-based e2e; no change to `make pre-pr`'s
  composition (the live track is additive, not folded into the pre-PR
  gate).
- No product-code, rule, or baseline changes — `tests/baseline_rules.json`
  is untouched (C-AQA-1).
