# NOTES.md — E2E test run & defect triage (branch `test/e2e-mock-and-live-triage`)

Environment: Windows 11, Python 3.11.9, fresh `.venv`, `pip install -e ".[dev]"`.
No source code was modified — this is investigation + reporting only.

## Runs executed

| Track | Command(s) | Result |
|---|---|---|
| **WITH MOCKS** (pytest suite: fixtures + `monkeypatch` edge cases + real-subprocess CLI calls) | `pytest tests/ --cov=openspec_graph --cov-branch --cov-report=term-missing --cov-report=json:coverage.json -q` + `tools/check_coverage_floor.py` + `tools/check_branch_coverage.py` | **343 passed, 11 failed** (354 collected). Line coverage 98.3% (floor 90%). Branch coverage 97.9% (floor 80%). Both floors pass. |
| **WITHOUT MOCKS** (live CLI, real self-validation — mirrors CI's `self-validate` job) | `planlint --target . detect` / `validate --fail-on ERROR` / `graph --format json` / `validate --fail-on WARN --json` | All exit 0. `20 spec(s) checked · 0 error · 0 warn · 0 info` — **PASS**, but see **Defect D** below, found by deliberately varying the encoding environment around this same command. |
| Supplementary gates (this repo's own definition of done, run directly since `make` is unavailable on this box — see Defect C) | `ruff check`, `mypy openspec_graph tools`, `tools/check_secrets.py`, `tools/check_docs.py`, `tools/check_no_hardcoded_thresholds.py` | All 5 pass clean. |

Raw logs kept out of the repo (per project convention — scratch outputs, not durable state): `with_mocks_pytest.log`, `without_mocks_live.log`, `supplementary_gates.log`, `ascii_repro.log`, `graph_head.json`, `validate_warn.json`, `coverage.json`, in this session's scratchpad directory.

---

## Defect A — Windows path separator leaks into tool output (Major, product bug)

**Symptom:** 8 of the 11 pytest failures assert a forward-slash relative path (e.g. `"openspec/changes/c1/specs/cap1/spec.md"`) and get a backslash one back (`'openspec\\changes\\c1\\specs\\cap1\\spec.md'`).

**Failing tests:**
- `tests/test_ledger.py::test_build_ledger_captures_rule_path_line_reason`
- `tests/test_ledger.py::test_build_ledger_orders_by_path_then_line_then_rule`
- `tests/test_ledger.py::test_build_ledger_relativizes_path_against_root`
- `tests/test_ledger.py::test_build_ledger_falls_back_to_the_full_path_when_not_under_root`
- `tests/test_enterprise.py::test_graph_relative_to_outside_root_falls_back`
- `tests/test_enterprise.py::test_finding_render_when_path_outside_root`
- `tests/test_graft.py::test_adr_source_name_uses_the_real_directory_name_when_present`
- `tests/test_graft.py::test_g009_fires_for_a_declared_adr_no_spec_cites`
- plus **`tests/test_decomposition.py::test_output_byte_identical`** (downstream symptom, not independent — see RCA)

**Root cause (confirmed by reading source):** several places compute a "repo-relative path" for display/JSON via `str(path.relative_to(root))` (or f-string-interpolate a `Path` object directly), instead of `path.relative_to(root).as_posix()`. `str(pathlib.Path)` renders with the platform-native separator — identical to `.as_posix()` on POSIX, but backslash-separated on Windows.

Exact sites, all the same bug pattern:
- [openspec_graph/graph.py:297-301](openspec_graph/graph.py#L297) — `_relative_to()`, feeds `graph --format json`/`mermaid`
- [openspec_graph/ledger.py:54-58](openspec_graph/ledger.py#L54) — private `_relative` helper, feeds `planlint waivers`
- [openspec_graph/rule_types.py:39](openspec_graph/rule_types.py#L39) (`Finding.as_dict`, feeds `validate --json`) and [rule_types.py:44-52](openspec_graph/rule_types.py#L44) (`Finding.render`, feeds human-readable `validate` lines)
- [openspec_graph/detect.py:99-113](openspec_graph/detect.py#L99) — `StackProfile.adr_source_name`, feeds G008/G009 rule messages

**Why `test_output_byte_identical` is the same bug, not a 4th independent one:** that test's own `_run_cli()` helper only does `stdout.replace(str(root), "<ROOT>")` — it strips the absolute temp-dir prefix but does nothing to normalize separators *inside* relative path segments. `validate --json` and `graph --format json` both embed paths built by the sites above, so their hashes drift; `rules --json` lists the static rule registry (no file paths at all), so it's untouched — exactly the pattern observed (`rules` hash matched, `validate`/`graph` didn't). Confirmed by reading `tests/test_decomposition.py:76-90`.

**Why this has never been caught:** `.github/workflows/ci.yml` pins all 5 jobs to `runs-on: ubuntu-latest`. There is no Windows leg in the CI matrix, so this is a latent defect, not a regression.

**Impact:** any native-Windows user or Windows CI agent running `planlint` gets backslash paths in: human-readable `validate` output, `validate --json`, `graph --format json`/`mermaid`, `planlint waivers`, and G008/G009 messages. Breaks exact-match consumers (this project's own test suite proves that), and is inconsistent with the forward-slash convention essentially every other cross-platform dev tool uses for portable output (git, ruff, eslint, etc.).

**Suggested fix direction (not applied):** replace `str(x.relative_to(root))` with `x.relative_to(root).as_posix()` at the four sites above. Narrow, mechanical, no behavior change on POSIX.

---

## Defect B — Symlink fixtures can't be created on Windows without elevated privilege (Minor, test-infra gap — not a product bug)

**Failing tests:**
- `tests/test_witness.py::test_load_witnesses_skips_a_dangling_symlink_without_raising` ([tests/test_witness.py:115](tests/test_witness.py#L115))
- `tests/test_graft.py::test_adr_directory_read_error_is_skipped_not_crashed` ([tests/test_graft.py:575](tests/test_graft.py#L575))

**Root cause:** both tests call `Path.symlink_to()` unconditionally to build a dangling-symlink fixture. Windows requires either Administrator rights or Developer Mode enabled (`SeCreateSymbolicLinkPrivilege`) to create *any* symlink, unlike POSIX where an unprivileged user always can. This account/sandbox has neither, so `os.symlink()` raises `OSError: [WinError 1314] A required privilege is not held by the client`. Neither test has a `pytest.mark.skipif`/try-except guard for this.

**This is not evidence of a product regression.** Both tests exist specifically because a *real* bug (uncaught `FileNotFoundError` crashing `detect.profile()` on a broken symlink) was found and fixed per PR #13 — the comments in both tests say so directly. The fix itself can't be re-verified on this machine; the gap is purely "this test suite cannot construct its own fixture here," not "the fix is broken here."

**Why missed:** Ubuntu CI runners always permit unprivileged symlink creation, so this never surfaced.

**Suggested fix direction (not applied):** `@pytest.mark.skipif(condition=<no symlink privilege>, reason=...)`, or wrap the fixture-building `symlink_to()` call in a try/except `OSError` → `pytest.skip(...)`, so the suite degrades gracefully on Windows instead of failing.

---

## Defect C — `test_typecheck_passes_on_clean_repo` hard-depends on a `make` binary that isn't guaranteed on Windows (Minor, test-infra/tooling gap — not a typecheck defect)

**Failing test:** `tests/test_enterprise.py::test_typecheck_passes_on_clean_repo` ([tests/test_enterprise.py:222-227](tests/test_enterprise.py#L222))

**Root cause:** the test unconditionally shells out to `subprocess.run(["make", "typecheck"], ...)` with no `shutil.which("make")` guard. This Windows box has no `make` on `PATH` at all (confirmed independently: `make --version` → `command not found`), so the subprocess call itself fails to launch: `FileNotFoundError: [WinError 2] The system cannot find the file specified`. This is the only `["make", ...]` subprocess call site in the whole test suite (verified by grep) — the gap is isolated, not systemic.

**Confirmed NOT a typecheck defect:** running the gate directly, bypassing `make` entirely —
```
mypy openspec_graph tools
Success: no issues found in 31 source files
```
— passes clean. The thing this test is meant to protect is completely healthy on Windows; only the `make`-shelling mechanism is unavailable here.

**Suggested fix direction (not applied):** either `pytest.mark.skipif(shutil.which("make") is None, ...)`, or have the test invoke the underlying `mypy openspec_graph tools` command directly instead of shelling out to `make`, so the assertion doesn't depend on an external build tool being installed.

---

## Defect D — CLI crashes on `validate` under an ASCII-only stdout encoding (High severity, product bug — found via the "without mocks" live track, not by either automated suite as currently written)

This is the most significant finding of the session and was **not** surfaced by running the existing test suite or the existing CI commands verbatim — it required actually varying the live execution environment, which is exactly what the "without mocks" live track is for.

**What happened:** the live self-validate run (`planlint --target . validate --fail-on ERROR`) exited 0 and printed:
```
20 spec(s) checked · 0 error · 0 warn · 0 info
```
When that output (redirected to a file, as any CI log capture would do) was read back, the `·` separators showed up as `�`. Investigating the raw bytes showed the file legitimately contains `\xb7` — a single byte, valid under Windows codepage 1252 (`·` = U+00B7 MIDDLE DOT), but **not valid UTF-8**, so any UTF-8-assuming viewer (this session's own tools included) renders it as the replacement character. That in itself is a real but cosmetic finding: `sys.stdout.encoding` on this box is `cp1252` (confirmed via `python -c "import sys; print(sys.stdout.encoding)"`), and `planlint` never forces UTF-8.

**Escalating from cosmetic to a confirmed crash:** reproduced directly —
```
$ PYTHONIOENCODING=ascii planlint --target . validate --fail-on ERROR
Traceback (most recent call last):
  ...
  File "openspec_graph\cli.py", line 235, in cmd_validate
    print(
UnicodeEncodeError: 'ascii' codec can't encode character '\xb7' in position 21: ordinal not in range(128)
```
Exit code 1 — at the exit-code level this is indistinguishable from "validation found errors," but it is actually an **unhandled crash on the tool's single most common command**, triggered by a realistic (not contrived) environment: any system where `sys.stdout`'s encoding can't represent U+00B7 — plain ASCII, a `LANG=C`/POSIX locale, or a Windows console codepage that lacks the glyph. Some CI systems and hardened images pin `PYTHONIOENCODING=ascii` deliberately for output-determinism reasons, which is directly in this project's own stated design philosophy (hermetic, deterministic tooling) — making this a realistic hazard, not an edge case.

**Root cause:** [openspec_graph/cli.py:236-237](openspec_graph/cli.py#L236) (and similarly lines 120, 144, 157, 240, plus non-ASCII characters elsewhere in the CLI's user-facing strings) hardcode `·` (U+00B7) and em-dash characters in `print()` calls, with no explicit stdout encoding configuration anywhere in the package (`grep -r "reconfigure\|PYTHONIOENCODING"` over `openspec_graph/` returns nothing). `print()` encodes using the ambient `sys.stdout.encoding`, which is locale/platform-dependent.

**This is a narrow, specific gap, not a sweeping codebase problem** — every file read/write in the package (`parse.py`, `detect.py`, `scaffold.py`, etc.) already explicitly passes `encoding="utf-8"` (verified by grep across the whole package). The one place that doesn't is stdout printing. That consistency elsewhere suggests the encoding was simply never considered for `print()`, likely because the project's only tested environment (Ubuntu CI) never triggers it: Python's PEP 538 automatically coerces a `C`/`POSIX` locale to `C.UTF-8` on Linux, so this class of bug is effectively invisible there. The project's own `Dockerfile` (`python:3.12-slim`) is likely unaffected for the same reason — this defect is specific to Windows and to explicit non-UTF-8 locale pins, not to the project's Linux/Docker path.

**Why neither automated track caught it:** the pytest suite's `run_cli()` helper spawns subprocesses that inherit the same ambient parent-process encoding (`cp1252` throughout this session) and nothing in the suite or CI ever varies `PYTHONIOENCODING`/locale, so the crash condition is never exercised.

**Suggested fix direction (not applied):** force UTF-8 for stdout explicitly (e.g. `sys.stdout.reconfigure(encoding="utf-8")` at CLI entry, or set `PYTHONUTF8=1` semantics programmatically), and/or replace the non-ASCII punctuation in output strings with ASCII-safe equivalents (`-` / `*` instead of `·`/`—`) so the tool degrades gracefully regardless of ambient encoding.

---

## Summary table

| # | Defect | Track found | Category | Severity |
|---|---|---|---|---|
| A | Backslash paths leak into `validate`/`graph`/`waivers`/G008-G009 output on Windows | With-mocks (8 tests) | Product bug (portability) | Major |
| B | Dangling-symlink test fixtures can't be built without Windows elevated privilege | With-mocks (2 tests) | Test-infra gap | Minor |
| C | One test hard-depends on a `make` binary not present on this Windows box | With-mocks (1 test) | Test-infra/tooling gap | Minor |
| D | `validate` crashes with `UnicodeEncodeError` under an ASCII-only stdout encoding | Without-mocks (live, deliberate env variation) | Product bug (crash) | High |

No defects found in: lint (ruff), typecheck (mypy, run directly), secret scanning, docs-check, hard-coded-threshold check, or the live self-validation happy path itself.
