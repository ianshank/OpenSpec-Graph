# Changelog

All notable changes to OpenSpec-Graph follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed — stdout encoding crash under a non-UTF-8 console (`fix-stdout-encoding-crash` change package)

- **`cli.py`'s `main()`**: `print()` calls — hardcoded punctuation
  (`·`/`—`) and arbitrary non-ASCII content echoed from a user's own spec
  files (e.g. `graph --format mermaid` node text) — relied on the ambient
  `sys.stdout`/`sys.stderr` encoding with no explicit configuration,
  reproducibly raising `UnicodeEncodeError` under `PYTHONIOENCODING=ascii`
  on `validate`, the single most common command. Fixed by forcing UTF-8
  on both streams once, at the CLI's one entry point, ahead of every
  subcommand — covers the open-ended user-content case, not just the two
  hardcoded characters, and degrades gracefully (`try`/`except`) rather
  than raising if a stream cannot be reconfigured (e.g. already closed).
  JSON output was already unaffected (`json.dumps(..., ensure_ascii=True)`
  by default).

### Fixed — Windows path separator leak (`fix-windows-path-separator-leak` change package)

- **Cross-platform relative-path output**: twelve sites across `graph.py`,
  `ledger.py`, `rule_types.py`, `detect.py`, `scaffold.py`, and `cli.py`
  computed a repo-relative path for display/JSON via
  `str(path.relative_to(root))` (or an f-string interpolating a `Path`
  directly) instead of `.as_posix()`, so every Windows run of
  `validate`/`graph`/`waivers`, and the G008/G009 rule messages, emitted
  backslash-separated paths — and `init` persisted a backslash-separated
  `invariant_source` into `openspec/specgraph.json`/`project.md` (an
  informational snapshot, never read back by `planlint` itself — Windows
  users who ran `init` before this fix can regenerate both files with
  corrected paths via `planlint init --force`). Never caught because
  `.github/workflows/ci.yml` only ran on `ubuntu-latest`. Fixed by a
  single new function, `detect.to_posix_relative(path, root)`, applied at
  every call site; absolute paths (`StackProfile.root`/`openspec_root`,
  `validate --json`'s `target` field, and `Finding.as_dict()`'s `path`
  field) are deliberately left in native form, since none of them is ever
  portable or cross-machine-comparable regardless of separator — so
  `validate --json`'s `"path"` field is the one output this fix does
  *not* change on Windows.
- **`validate`'s plain-text finding order is now OS-independent**: the
  findings sort key also moved off `str(f.path)` onto the same shared
  function, since `\` sorts after digits/uppercase letters while `/`
  sorts before them — two sibling change directories (e.g. `add-thing`/
  `add-thing2`) could otherwise render in opposite order on Windows vs.
  POSIX for an identical repo.

### Added — witness mode / CP-WM (`add-witness-mode` change package)

- **New rules `W001`/`W002`** (both ERROR, evaluated only under
  `--require-witness`): `W001` — a spec's cited stage has no fresh, exit-0
  witness, with a distinct message for "never witnessed," "witnessed but
  not at the current commit," and "witnessed but failing" rather than one
  generic message. `W002` — a witness that already clears W001's own bar
  records coverage below the detected floor. Applies to both dialects,
  including a scenario citing more than one stage (each requiring its own
  witness). 22 rules total (was 20).
- **`planlint witness --stage <name> --exit <code> [--coverage <pct>] --sha
  <sha>`**: records one witness as a content-addressed file under
  `.planlint/witnesses/` (new `openspec_graph/witness.py`, atomic write,
  fail-closed load). Full boundary validation — a full 40-character sha
  (an abbreviated one is rejected, never silently non-matching), a finite
  in-range coverage, a valid stage identifier — before anything is
  written, and a clean exit-2 message rather than a traceback on an
  unwritable store.
- **`validate --require-witness`**: fails closed on a repo with zero
  witnesses; default `validate` behavior is completely unchanged without
  the flag — the entire pre-existing test suite passes unmodified against
  the new, defaulted `rules.evaluate(rule_set=...)` parameter. `graph`'s
  `broken_links` and rendered output never include W001/W002 findings,
  under any flag.
- Two design rounds before any code was written: an initial re-grounding
  pass found the committed roadmap sketch (`docs/differentiation-roadmap.md`'s
  `CP-7` section) hadn't survived contact with the current codebase — a
  flag collision with the global `--target`, an architecturally impossible
  touch-map claim, an unspecified "signed" claim with no key-management
  story anywhere. A dedicated adversarial peer review of the rewritten
  design then found a real HIGH-severity bug introduced during that
  rewrite itself — a short-commit-sha comparison that would have silently
  defeated freshness checking for any CI script using an abbreviated sha —
  plus a wider set of gaps, all resolved before implementation began.
- **Fixed, found during that same adversarial review:** the pre-existing
  `Criterion.verified_by` waiver-comment leak (open since before this
  change, for both dialects) is wider for the upstream dialect than
  harness — any waiver comment anywhere in a Scenario's block could leak a
  spurious stage citation into `verified_by`. Fixed for both dialects,
  landed before W001/W002 existed to consume it.
- `tests/test_rule_registry_docs.py` extended to the new `W` family.
  `docs/differentiation-roadmap.md`'s `CP-7` sketch replaced with a proper
  "implemented" section, mirroring how CP-GV/CP-AD each got their own late
  addition.

### Added — architecture drift lint / CP-AD (`add-architecture-drift-lint` change package)

- **New rules `G008`/`G009`** (both WARN): `G008` — a spec cites an `ADR-n`
  id not declared in the detected ADR source. `G009` — a declared ADR cited
  by no living spec anywhere, and not waived. Mirrors G005/G006 exactly. 20
  rules total (was 18).
- ADR discovery (`detect._adrs()`): tries a fixed, most-specific-first
  candidate list (`docs/adr`, `docs/architecture/decisions`,
  `docs/decisions`, `adr`, `docs/ADR.md`), supporting either a directory of
  per-decision files or a single index file — unlike the single-file
  `_invariants()` template, matching real-world ADR practice. Ids come from
  scanning each candidate's own text, never filenames, so a zero-padded
  filename can't silently mismatch a spec's bare citation.
  `StackProfile.adr_source`/`adr_ids` threaded into both `to_card()` and
  `dialect_card._COMPARABLE_FIELDS`.
- `graph.py` gains its first new node type since the original five: `adr`,
  reusing the existing `declares` edge type. An orphaned ADR gets graph
  representation the same way an orphaned invariant already does.
- New `tests/test_rule_registry_docs.py`: a single pytest test guarding
  every prose claim about the rule registry's count or per-family id range
  (README's table, `c4.md`, `docs/agents-skills-harness.md`,
  `docs/next-steps.md`, `docs/differentiation-roadmap.md`, `rules.py`'s own
  module docstring) against `rules.RULES` itself — added after the third
  independent recurrence of this exact drift class in this codebase's
  history (`c4.md` twice, then `rules.py`'s own docstring, found live
  during this change's own design).
- **Scoped to ADR only.** OpenAPI operationId and event-schema id
  citation-checking, and a `c4.md`-doc-freshness rule pair, are explicit
  non-goals this round — not partial or stubbed work, and no rule ident is
  reserved for either. See the change package's own Non-Goals and Decisions
  for the full reasoning.
- `docs/differentiation-roadmap.md` gains a proper CP-AD section, mirroring
  how CP-GV got its own late addition.
- **Fixed, from GitHub's automated review on the PR:** ADR directory
  discovery no longer promotes a file's *reference* to another decision
  ("Supersedes ADR-99") into a *declaration* of it — only a file's own
  first mention (its title) counts. A waiver's own reason text can no
  longer satisfy the citation it's waiving (the identical bug already
  existed, unfixed, for `INV_REF` since CP-4). `dialect_card.diff_cards()`
  no longer reports a field entirely absent from an older, pre-upgrade
  card as false repository drift against the new card's default value — a
  latent bug present since this schema's first additive field, not new to
  CP-AD. `ParsedSpec.adr_refs` was moved to strictly after the existing
  `raw` field, since inserting it earlier would have silently shifted
  `raw`'s positional index for any caller of the publicly-exported
  `ParsedSpec` still constructing it positionally.
- **Fixed, from an adversarial code review:** ADR directory discovery no
  longer crashes `detect.profile()` (and therefore every CLI verb) when a
  candidate directory contains a dangling symlink — `glob("*.md")` matches
  a broken symlink by name alone, so the read is now guarded and an
  unreadable entry is skipped like any other non-declaring file (the same
  guard was added to `_invariants()`'s read for the equivalent
  permission-denied case). The "a file's first `ADR-n` mention is its
  declaration" heuristic now prefers the first mention on a markdown
  heading line over an earlier body reference, closing a residual gap in
  the fix above it: a file whose body opens with "Related: ADR-1" before
  its own `# ADR-2: ...` heading no longer gets `ADR-1` mistaken for its
  declared id.

### Changed — architecture doc converted to Mermaid diagrams

- `docs/architecture/c4.md`'s Context, Container, and Module-map diagrams
  (previously ASCII art in `text` fences) are now real Mermaid flowcharts,
  and the Data-flow section gained a new pipeline diagram alongside its
  existing prose. Every diagram was validated for correct Mermaid syntax
  before landing. `tests/test_rule_registry_docs.py`'s module-map
  family-range check was generalized to match the new format (no longer
  requires the old ASCII tree's `# G001-G009`-style Python-comment
  formatting) while still guarding the same underlying fact against
  `rules.RULES`.

### Added — Mermaid graph export / CP-GV (`add-mermaid-graph-export` change package)

- **`planlint graph --format mermaid`**: renders the dependency graph as a
  Mermaid flowchart instead of JSON — GitHub/GitLab render it inline, so a
  PR diff on `openspec/` can carry an actual picture. Real node ids (which
  contain slashes/dots) are sanitized to synthetic identifiers; orphan and
  missing (`exists: False`) nodes get distinct styling, and broken
  (`finding`/`exists: False`) edges get a distinct `linkStyle` — spotting a
  broken link is the entire point of a picture over raw JSON.
  `--format dot` (image rendering, needing an external engine) stays
  rejected exactly as before; this doesn't reopen that non-goal, only adds
  to it.
- **`planlint graph --change <name>`**: scopes which specs are rendered as
  nodes/edges, a capability `validate` already had that `graph` didn't. The
  whole-tree orphan-invariant check always still runs unscoped regardless
  of what's rendered — scoping both would have reproduced the exact
  false-positive-orphan bug `validate --change` already guards against.
  Prints its own `INFO` note (mirroring `validate --change`'s own G006
  note) since a nonzero `broken_links` count under `--change` can reflect
  an invariant issue entirely outside the rendered scope.
- New `openspec_graph/mermaid.py` (pure, stdlib-only) and companion
  `tools/render_mermaid.py` (renders a previously-saved `graph --format
  json` artifact without re-running `planlint`).
- `detect.filter_by_change()`: the `--change` path filter, previously
  inline only in `cmd_validate`, extracted and now shared by `graph` too.
  Matches the fixed structural position of the
  `changes/<name>/specs/<capability>/spec.md` convention rather than
  scanning for the first/any `"changes"` path segment, which was imprecise
  against a change name colliding with another path segment (found and
  fixed twice over during review — first for a change named `"specs"`,
  then again, one level down, for a change named `"changes"` itself).

### Fixed — repo hygiene sweep (gitleaks, tooling parity, doc/code drift)

- **`.gitleaks.toml` was silently disabling real secret detection.** A
  gitleaks `--config` file replaces its entire built-in ruleset unless it
  explicitly extends it; this file had no `[extend]` block, so `make
  security` had been running gitleaks with effectively zero detection rules
  (an allowlist with nothing to check against) since gitleaks was
  introduced. Verified experimentally with the real binary, before and
  after: a planted example secret went from "no leaks found" to "leaks
  found: 1" once `[extend]\nuseDefault = true` was added.
- `.dockerignore` brought into parity with `.gitignore`'s coverage (`env`,
  `.dmypy.json`/`dmypy.json`, `.coverage.*`, `*.cover`, `*.egg`, the
  CI-produced JSON artifacts, editor/OS cruft) — previously narrower, so a
  stale local artifact could leak into a Docker build context.
- `Makefile`: the `python tools/check_no_hardcoded_thresholds.py` call that
  previously lived only inline inside `pre-pr`'s recipe is now its own
  named `.PHONY` target (`thresholds`), matching every other gate's shape
  and making it wireable into a pre-commit hook. New `graph-mermaid`
  target.
- `.pre-commit-config.yaml`: two new local hooks, `make docs-check` and
  `make thresholds`, closing the gap where those two CI-hard gates could
  previously fail only at push/CI time, never at commit time.
- `StackProfile.invariant_source_name`: a new computed property shared by
  G005 (`rules_generic.py`) and G006 (`rules.py`), replacing two
  independent copies of the same "real file name, or 'the contract' as a
  fallback" logic that could otherwise silently drift apart.
- `docs/architecture/c4.md`: two `broken_links == validate findings`
  invariant claims corrected — both were stated unconditionally, but
  `graph --change` and `validate --change` deliberately disagree on this by
  design (`DEC-GV-002`); the claims now state the unscoped-run scope they
  actually hold under.
- `openspec/changes/add-mermaid-graph-export/tasks.md`: corrected a stale
  test-count claim ("10 new tests" in `tests/test_graph.py`; the commit
  that shipped actually added 8, confirmed against the real diff).
- `docs/hooks.md`: documented the two new pre-commit hooks, and added an
  "Adding a new pure derived-output module" recipe naming the
  `dialect_card.py`/`ledger.py`/`mermaid.py` pattern — previously only
  "Adding a custom rule" had a documented extension recipe.

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
