# Changelog

All notable changes to OpenSpec-Graph follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — waiver ledger and invariant lints / CP-4 (`add-waiver-ledger-and-inv-lints` change package)

- **New rule `G007`** (ERROR): a waiver (`<!-- specgraph:allow RULE reason -->`)
  with no reason text now fails the gate — previously waivers were silently
  downgraded to INFO regardless of whether a reason was given. A comment
  naming multiple rules fires one independent G007 finding per rule name.
  G007 cannot be silenced by waiving itself with no reason.
- **`parse_semantics.Waiver`/`parse_waivers`**: the waiver regex always
  captured the reason text; `suppressions()` discarded it. `ParsedSpec`
  gains an additive `waivers: tuple[Waiver, ...]` field (rule, reason,
  line) alongside the existing `suppressed` set, which is now derived from
  it rather than computed separately.
- **New rule `G006`** (WARN): a declared invariant cited by no living spec,
  and not waived, is now reported as an orphan — invariant citation was
  previously checked in only one direction (G005: a cited invariant must be
  declared). This is the first rule in the codebase that is a property of
  the whole spec tree rather than one file; a new `rules.evaluate_tree()`
  runs once per `validate`/`graph` call after every living spec is parsed.
  Skipped (with an `INFO` note) under `validate --change`, since a
  `--change`-filtered view would otherwise report invariants cited outside
  that view as falsely orphaned. `Finding` gains an additive `subject`
  field (the orphaned invariant id) and `graph`'s exported nodes now
  include orphan invariants (`orphan: true`) that no spec cites.
- 18 rules total (was 16).
- **New `planlint waivers --format json` verb** (AC-WL-1): a stable-ordered
  ledger of every waived rule across the whole tree, with file, line,
  reason, and the owning change package. New `openspec_graph/ledger.py`
  (pure aggregation, no file I/O) does the work; the CLI layer reads
  `openspec/`, parses every living spec, and prints text or JSON. Exits 2
  with no `openspec/` tree, same as `validate`/`graph`. Pure reporting,
  like `detect`/`graph`/`rules` — never fails on content, only on usage
  errors; enforcement stays G007/`validate`'s job.

### Added — dialect cards / CP-2 (`add-dialect-cards` change package)

- **`planlint detect --format json`**: emits a stable, schema-versioned
  "dialect card" — a portable projection of the detected profile
  (dialect, languages, make targets + confidence, coverage-floor locator,
  invariant source/ids) that deliberately excludes every absolute-path
  field (`root`, and `openspec_root` reduced to a portable
  `has_openspec_root` boolean). Proven byte-identical not only across two
  runs but across the same logical repo checked out at two different
  absolute paths. The existing `--json` flag is unchanged — still the
  full profile, `root` included, for backward compatibility.
- **`planlint detect --diff <prev.json>`**: compares a previously-saved
  card against the current one and exits non-zero listing exactly which
  fields changed, or 0 with `PASS: no drift in detected conventions`.
  Mirrors `tools/diff_spec_graph.py`'s existing `PASS`/`FAIL` vocabulary.
  A missing or malformed baseline is a usage error (exit 2), never a crash.
- **`openspec_graph/dialect_card.py`** (new): pure, stdlib-only,
  zero-intra-package-import schema + diff module (`SCHEMA_VERSION`,
  `diff_cards`), mirroring `machinery.py`'s isolation precedent.
- Spot-checked against this repo's own Makefile: `planlint detect --format
  json` then `--diff`-ing that same output reports "no drift," as expected.

### Fixed — Makefile `define`/`endef` block misparse (`fix-makefile-define-block-misparse` change package)

- **`machinery.py` and `detect.py`'s legacy-regex fallback**: a
  `define...endef` block's body is commonly written at column 0 with no
  leading tab, so a body line like `Usage: make test` matched the rule-line
  pattern in both parsers, fabricating `"Usage"` as a target that doesn't
  exist — which could cause G004 to silently pass a spec citing a target
  that isn't real. Both the structural parser and the low-confidence
  regex fallback it widens with had the identical blindness; fixing one
  without the other left the end-to-end `detect.profile()` path broken.
  A `define` block now lowers `MakefileFacts.confidence` to `"low"`,
  matching the existing `include`/conditional precedent.

### Fixed — subprocess coverage blind spot (`fix-subprocess-coverage-blind-spot` change package)

- **Coverage measurement**: `tests/support.py`'s `run_cli()` tests the CLI
  as a real subprocess; with no `COVERAGE_PROCESS_START`/`parallel`
  configuration, pytest-cov was structurally blind to every line reachable
  only through those calls — the previously-reported ~96%/~92%
  line/branch coverage was a floor, not ground truth. `[tool.coverage.run]
  parallel = true` fixes the gap by activating pytest-cov's own
  auto-installed subprocess-coverage hook (a `.pth` file it drops into
  site-packages; no project-specific hook file needed — an initial draft
  added a `sitecustomize.py` believing it was necessary, but an
  independent review found it non-functional and redundant, confirmed by
  removing it and observing identical coverage). Total coverage rose to
  96.95% purely from already-tested paths becoming visible. Surfaced (and
  fixed) six real, previously-invisible gaps: a false-negative test that
  passed for the wrong reason
  (`test_cli_validate_change_not_found`), one line of dead code in
  `parse.py`, and four genuinely correct but untested branches (a
  harness-to-upstream per-file fallback, two malformed-config fallthrough
  paths, the zero-Makefile end-to-end path, and G001's "neither" branch).

### Changed — `init` snapshot wording (`fix-init-snapshot-wording` change package)

- **`specgraph.json`/`project.md`**: generated content and CLI help text
  described these files as something that "pins" or is "authoritative"
  for detected conventions, but nothing ever reads either back — `detect`
  always re-derives fresh from the filesystem, by design. Wording-only fix
  (zero behavior change): both now describe themselves as a snapshot
  recorded at `init` time, not a live config.

### Added — `--version`/`-V` CLI flag (`add-cli-version-flag` change package)

- **`planlint --version` / `-V`**: prints the installed version and exits
  0. Resolved from installed package metadata
  (`importlib.metadata.version("openspec-graph")`), falling back to the
  package's own `__version__` constant only for an uninstalled checkout —
  self-correcting against drift rather than a third hardcoded copy.

### Added — parse repo machinery structurally / CP-3 (`parse-repo-machinery-structurally` change package)

- **`openspec_graph/machinery.py`**: new stdlib-only, zero-intra-package-import
  structural Makefile parser (`MakefileFacts`, `parse_makefile()`). Resolves
  shared multi-target lines (`foo bar: baz`) as distinct targets — the
  previous regex silently dropped every name on such a line — and the full
  12-name GNU Make special-target set (the previous regex's `[a-zA-Z]`-only
  first character made 9 of the intended 12 unreachable). Never shells out
  to `make` under any condition: GNU Make evaluates `$(shell ...)` at
  parse/read time unconditionally, so no flag combination (`-p`/`-n`/`-q`)
  makes shelling out to a real `make` safe against an untrusted target
  repo's Makefile. Verified by an executable test, not just design review:
  a fixture with a `$(shell touch <marker>)`-in-target-position payload,
  `subprocess.run`/`Popen` patched to raise if called at all. 100%
  line/branch coverage on the new module.
- **Wired into `detect.py`**: `_make_target_facts()` calls the structural
  parser and, only when confidence is low (an `include`, a conditional, or
  variable expansion was seen), widens — never replaces — with the
  pre-existing regex fallback, so a target resolved correctly is never lost
  because something else in the file couldn't be. `StackProfile` gains
  additive `make_target_confidence`/`make_unresolved_count` fields (JSON
  shape of the existing `make_targets` field is unchanged); `planlint
  detect` reports an `INFO` notice on low-confidence parses.
  `rules_generic._unknown_make_target` (G004) needed no source changes —
  the widening happens centrally, so G004, `graph.py`, and
  `scaffold.pick_stage()` all see the same resolved picture.
- **G003 value-comparison**: `_hard_coded_threshold` now suppresses a
  finding only when a single, unambiguous, matching threshold-shaped number
  is on the offending line — never "the real value appears somewhere on the
  line," which would wrongly excuse a genuine violation sitting next to an
  unrelated, coincidentally-matching number.
- **`MAKE_REF` tightened**: requires backtick-fencing (was optional both
  sides), so bare English "make sure"/"make progress" in ordinary spec
  prose no longer false-cites a target.
- **`docs/differentiation-roadmap.md`**: swept for stale `AC-PM-*`/`make -p`
  -viable-with-fallback references that predated and contradicted the
  above safety decision, and a G002/G001-vs-G003/G004 mislabel.
- 27 new tests across `tests/test_machinery.py` (13, new), `tests/test_graft.py`
  (12, new/modified), and `tests/test_decomposition.py` (2, new) — 156 total.

### Fixed — coverage-floor detection gap (`fix-coverage-floor-detection-gap` change package)

- **`.coveragerc`/`setup.cfg` support**: `detect._threshold()` was silently
  blind to both standard Python coverage-config locations, checking only
  governance-policy.json candidates and `pyproject.toml`. Added
  `configparser`-based detection for both (different section names per
  coverage.py's own convention — bare `[report]` in `.coveragerc`, namespaced
  `[coverage:report]` in `setup.cfg`); additive-only precedence —
  `pyproject.toml` still wins when present. `THRESHOLD_ALLOWLIST` extended
  so a spec legitimately citing either file by name isn't flagged by G003.

### Fixed — U004 body-blind modal check (`fix-u004-body-blind-modal-check` change package)

- **Upstream-dialect requirements**: rule U004 ("requirements are
  normative") only ever checked a requirement's heading line for
  SHALL/MUST, never its body paragraph, because the parsing regex couldn't
  cross a newline. `Requirement` gains a `body` field and an `is_normative`
  property checking both. Measured against a real external repo during
  validation: 20 of 34 requirements previously false-fired under this bug,
  because their normative sentence lived in the body below a noun-phrase
  heading — the common real-world authoring style this project's own
  scaffold template happens to avoid, which is exactly why only
  self-referential test fixtures never caught it.

### Changed — rename CLI to `planlint` + positioning (`rename-cli-and-positioning` change package)

- **CLI renamed**: `specgraph` → `planlint` as the primary console script;
  `specgraph` remains as a deprecated alias (`main_deprecated`) that warns to
  stderr, delegates to `main`, and preserves the real exit code — old CI
  invocations never silently pass.
- **Backwards-compat contracts kept as `specgraph`**: the waiver syntax
  `<!-- specgraph:allow ... -->`, the `openspec/specgraph.json` config file,
  and the `[tool.specgraph]` pyproject section are stable identifiers, not
  renamed. The log-level env var accepts `PLANLINT_LOG_LEVEL` (preferred) and
  `SPECGRAPH_LOG_LEVEL` (legacy).
- **Positioning**: README leads with the wedge statement and a competitive
  positioning table; explicit non-goals section (not an authoring framework,
  IDE, MCP server, or autonomous agent).
- **`tests/test_cli_surface.py`**: verb allow-list guard (AC-RP-3 non-success —
  an authoring/propose/apply verb added to the CLI fails `make test`) plus
  deprecation-alias behavior tests.
- Not yet published to PyPI; install from source or `pip install git+https://github.com/ianshank/OpenSpec-Graph`.

### Changed — decompose god files (`decompose-god-files` change package)

- **Facade-preserving split**: `parse.py`, `rules.py`, `scaffold.py`, and
  `graph.py` were each split into focused submodules (`parse_model.py`,
  `parse_semantics.py`, `parse_harness.py`, `parse_upstream.py`;
  `rule_types.py`, `rules_generic.py`, `rules_harness.py`,
  `rules_upstream.py`; `scaffold_templates.py`; graph-building helpers), with
  the original modules kept as stable facades — public imports and CLI
  behavior are unaffected.
- **`tests/test_decomposition.py`**: guard tests locking public import
  compatibility, byte-identical `validate`/`graph`/`rules --json` output
  (path-normalized), and stable rule-set ordering — written before the
  production split, to catch any behavioral drift the refactor might cause.
- **`tests/support.py`**: shared test fixture helper, deduplicating a helper
  previously copy-pasted across test files.

### Changed — post-merge quality review (`post-merge-quality-review` change package)

- **Lint hygiene**: `Finding.render` uses `contextlib.suppress(ValueError)`
  (SIM105); `scaffold.plan_init` drops a dead assignment before `return`
  (RET504). Extended ruff families now report zero findings.
- **Type safety**: `graph.build_graph` carries `dict[str, object]` type
  arguments; `mypy --strict` on the package is clean (advisory, not a gate —
  DEC-PR-001).
- **No magic numbers in the graph contract**: node-text truncation is the named
  `NODE_TEXT_LIMIT = 200` constant (preserves the prior value exactly).
- **Reusable gate helpers**: `tools/_common.py` (`repo_root()`, `read_text()`)
  is shared by `check_docs.py`, `check_no_hardcoded_thresholds.py`, and
  `check_secrets.py` via the standalone-script `sys.path` bootstrap — repo-root
  discovery is now defined once.
- **Edge-case tests**: unknown `SPECGRAPH_LOG_LEVEL`, path-outside-root
  fallback, `init --dry-run`, and mixed-dialect warning. Branch coverage
  90.8% → 91.3%.
- **Structural guard tests**: AC-PR-3/4/6/8 are enforced by `make test`, not
  one-off grep — a regression reintroducing a bare `[:200]`, a duplicated
  repo-root literal, a third-party import in `_common.py`, or a forced
  pre-push hook in the Makefile/CI fails the suite. Logging-level assertions
  use `logging.WARNING`/`DEBUG`/`INFO` constants, not magic integers.
- **Docs**: optional pre-push hook in `docs/hooks.md`; deferred hooks/loops
  (watch loop, scheduled self-validation cron, pre-push) and skills/agents
  (entry-point rule registration) extension points in `docs/next-steps.md`.

### Added — enterprise hardening (`enterprise-hardening` change package)

- **`make pre-pr`**: one-command enterprise AQA gate (test + lint + typecheck +
  security + validate + docs-check + no-hardcoded-thresholds).
- **mypy** as a hard type-checking gate (`make typecheck`), config in
  `pyproject.toml` (`check_untyped_defs`, `warn_unused_ignores`).
- **gitleaks** secret scanning (`make security`) with a deterministic Python
  fallback when the binary is absent; `.gitleaks.toml` config; CI gitleaks job.
- **`tools/check_no_hardcoded_thresholds.py`**: fails if a numeric threshold or
  tool version is hard-coded in the Makefile or workflow YAML.
- **`tools/check_docs.py`**: fails if a required doc is missing or unlinked from
  README.
- **Structured debug logging**: `-v` / `--verbose` and `SPECGRAPH_LOG_LEVEL`
  emit diagnostics to stderr only; JSON stdout stays pure and parseable.
- **Deterministic JSON output** for `validate --json`, `graph --format json`,
  and `rules --json` (stable ordering), with regression tests locking it in.
- **Optional `Dockerfile`** + `.dockerignore` for hermetic CLI invocation.
- **`.pre-commit-config.yaml`** wiring ruff, mypy, gitleaks, and self-validation.
- Documentation: C4 architecture (`docs/architecture/c4.md`), AQA guide
  (`docs/aqa.md`), hooks (`docs/hooks.md`), the rules-as-deterministic-skills
  model (`docs/agents-skills-harness.md`), and next steps (`docs/next-steps.md`).

## [0.1.0] — 2026-08-30

### Added

- `specgraph` CLI: `detect`, `init`, `new`, `validate`, `graph`, `rules`.
- Rule engine: 16 rules (G001–G005, H001–H006, U001–U005) across harness and
  upstream dialects, with inline waiver support.
- Scaffolded OpenSpec change packages; graph export (pure projection of
  `validate`); `harden-ci-gates` coverage/lint/graph-diff gates.
- GitHub Actions CI: test matrix (3.10–3.13), self-validate hard gate,
  graph-diff regression gate on PRs.

[Unreleased]: https://github.com/ianshank/OpenSpec-Graph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ianshank/OpenSpec-Graph/releases/tag/v0.1.0
