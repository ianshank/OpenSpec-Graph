# Changelog

All notable changes to planlint follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — `delta`, which reports what *your change* broke

- **`planlint delta --baseline CARD.json`** compares a saved dialect card
  (`detect --format json`) against the live repository and lists every spec
  whose citations the machinery moved out from under: a make target removed
  since the baseline, an invariant or ADR no longer declared, or — the case
  the roadmap names — a spec still citing the coverage floor you just changed.
  Text or JSON, with the same schema-versioned envelope every other
  machine-readable output carries.
- **It is not a second `validate`.** A citation must have been *supported at
  the baseline* and be unsupported now. One that was already broken before the
  comparison began is `validate`'s finding (G004/G005/G008), not a delta.
  Without that attribution the verb would report the same things under a
  different name and leave a reader unable to tell which of them their own
  commit caused, so it is a requirement with its own test rather than a note.
- The baseline is a saved card rather than a git ref, deliberately. Reading
  machinery at a ref needs a second subprocess call site taking a
  user-supplied argument, which the existing safety argument for the only
  such call does not cover; and threshold, invariant and ADR discovery are
  multi-file scans over a root, not single files to `git show`. "Since a ref"
  is already available through the worktree pattern the graph-diff job uses.

### Added — SARIF output, a composite action, and pre-commit hooks

- **`validate --format sarif`** emits SARIF 2.1.0, so findings land inline on
  the pull-request diff a team already reviews instead of in a CI log nobody
  opens. `--json` is kept as an exact alias of `--format json`; pairing it
  with a different format exits 2 rather than silently picking one.
- The projection consumes the findings `validate` already computed, so "the
  same findings as `--json`" is true by construction rather than by a second
  implementation somebody has to keep in step. All three renderings share one
  sort order.
- **A `line` of 0 omits the region entirely, never clamping to 1.** This is
  the common path, not an edge case: no rule sets a line today, so clamping
  would put a wrong annotation on the first line of every file in every pull
  request — and a reviewer could not tell it was wrong. A finding with no path
  is emitted with an empty `locations` array rather than dropped; losing a
  result to satisfy a schema is the one failure this format must not add.
- **`.github/actions/planlint/action.yml`**, a composite action that installs
  a pinned planlint, reports detected conventions, and uploads SARIF — with
  the gate applied *after* the upload, so findings reach the diff even when
  the job fails. **`.pre-commit-hooks.yaml`** gives adopters a hook definition;
  it is distinct from this repository's own contributor-facing
  `.pre-commit-config.yaml`, and never invokes a `make` target an adopter
  does not have.
- **The adopter-URL guard now covers both.** Its corpus stopped at the skill
  tree and `templates/`, so the action's pinned install line would have been
  unguarded — the same gap that let a rename leave eight files printing a
  command for a name that no longer existed.

### Fixed — one spec on disk is discovered once

- **A symlinked change or feature directory no longer double-counts a spec.**
  `Path.glob()` follows a valid directory symlink, so a
  `specs/002-alias -> specs/001-foo` link yielded two distinct paths for one
  `spec.md`: `feature_dirs` reported two features for one, `specs_checked`
  over-reported, and the graph rendered duplicate `FR-001`/`SC-001` nodes for a
  single requirement. Both discovery functions and `profile()`'s separate
  `change_dirs` glob now deduplicate by real-path identity through one shared
  helper. Identity is the file, not its content: two distinct specs that read
  the same are still two specs.
- **The surviving name is the real directory's, not an alias's.** The first
  implementation kept the first path in sorted order, which was deterministic
  but arbitrary — `alias-change` sorts before `real-change`, so the alias
  survived and `--change real-change` reported "no specs found" while
  `--change alias-change` passed. The real path now wins, with ordering
  breaking ties only where no candidate is a real path. Two directories that
  are one package are addressable by one name, and it is the recognisable one;
  the alias name exits 2.

### Fixed — the exit-code contract now holds for unreadable specs

- **A spec that exists but cannot be read exits 2, not 1.** `parse_spec` read
  its bytes with no guard, so a permission-denied file, a broken mount, or a
  directory where a file belongs let an `OSError` escape to the top of
  `validate`, `waivers`, and `graph`. That printed a traceback and exited 1 —
  the code the contract reserves for "findings were reported" — so a CI job
  could not tell a broken checkout from a failing gate. The error is now
  translated to a typed `SpecReadError` at the one place specs are read, and
  every verb that parses specs renders it as one line naming the
  repository-relative path and the reason. The run aborts rather than
  reporting on the specs it could read: a spec skipped silently would pass a
  gate that never saw it. Same defect class as `DEC-SD-001`, one verb further
  in.
- **`--change` on a SpecKit target says why it found nothing.** The flag
  scopes OpenSpec change packages; the generic "no specs found" read as "your
  feature is missing" when the real answer is that the flag does not apply to
  a SpecKit `specs/` tree yet. Both verbs that accept the flag now render the
  message through one shared helper.

### Changed — `validate --json` is a portable, versioned artifact

- **The findings envelope carries `schema_version` and `tool_version`, and
  every finding path is POSIX-relative to the target.** Both the repository's
  own CI and the adopter-facing `templates/spec-gate.yml` upload this file as
  a build artifact produced on a runner and read elsewhere, where an absolute
  `/home/runner/work/...` path resolves to nothing. This supersedes
  `DEC-PS-002`, which kept the path absolute on the premise that no consumer
  compares the field across two checkouts; the shipped template refutes that
  premise. `Finding.as_dict()` takes an optional root and keeps its previous
  absolute rendering when none is given, so no other caller changed.
  Breaking for anyone parsing the old shape — and deliberately landed before
  the first release, while that is nobody.
- **Findings in the JSON are sorted the way the text renderer already sorted
  them.** The two renderings of one run agreed on content but not on order.
- **The package-version lookup is memoized.** argparse resolves it whenever a
  parser is built and the envelope needs the same value again, so the
  ambiguous-environment warning could print twice in a single run.
- **`detect --json` is deprecated** in favour of `detect --format json`, with
  a stderr notice and removal announced for 1.0. Its stdout is unchanged.

### Changed — licence metadata follows PEP 639

- **`pyproject.toml` declares an SPDX expression and a `license-files` glob**,
  with the build-system floor raised to `setuptools>=77` in the same commit
  and the redundant `License ::` classifier removed, which PEP 639 forbids
  alongside an expression. A wheel build went from four deprecation warnings
  to none. The migration was previously deferred for want of a provably clean
  build environment; `python -m build` resolves build requirements in an
  isolated environment, which makes the ambient `packaging` version
  irrelevant.
- **New gate `make wheel-check`** (`tools/check_wheel_metadata.py`) reads the
  built wheel and fails when the SPDX expression is missing or does not match
  `pyproject.toml`, when a legacy classifier survives, or when a declared
  licence file is absent or empty. It exits 2 when there are no wheels at all,
  because "nothing to check" must never read as "everything passed". The
  obvious criterion — that a build without a `LICENSE` file fails — was tested
  and is false: setuptools accepts a glob matching nothing and ships a wheel
  with no licence, silently. Wired into a new `packaging` job on every pull
  request, and into the release workflow before anything is uploaded to an
  index whose versions are immutable.

## [0.2.0] — 2026-09-02

> `v0.1.0` was tagged in git (`cdc94ca`) under the previous distribution name
> `openspec-graph`, and was never published to a package index. `v0.2.0` is the
> first release under the `planlint` name and the first intended for PyPI;
> publication happens when the tag is pushed and `.github/workflows/release.yml`
> runs.

### Added — adopter-facing guards and an agent entry point

- **`AGENTS.md`**: the pointer an agent loads on arriving in this repository.
  It names the gate command and defers to the Agent Skill for the verb surface
  and the refusal boundary rather than restating either. Wired into
  `tools/check_docs.py`, so it must exist and be linked from the README, and
  its links are resolved by a test — the same treatment `llms.txt` already had.
- **`tests/test_adopter_urls.py`**: holds every install command this repository
  prints to what it actually publishes. Files are discovered rather than
  listed, because the incident behind this test was eight places drifting and
  a hand-written list only ever covers the ones already fixed.
- **`tests/test_agent_artifacts.py` gains a root-markdown wiring check**: any
  markdown file at the repository root must be under the docs gate. This is the
  check that would have caught `AGENTS.md` shipping as an orphan.
- **A curated `ruff` `select` list.** Ruff's default selection is `E4/E7/E9/F`,
  so every other family — import sorting, bugbear, bandit, pyupgrade — was off,
  including the `S` rules the existing `per-file-ignores` already named. Each
  family enabled was at or near zero violations, so this locks in properties
  the code already had. `E501` stays off deliberately, with the reason and the
  measured backlog recorded in `docs/next-steps.md`.
- **Diagnostic logging in `detect.py`**, which previously had none despite
  owning every discovery decision. The coverage floor's six candidate
  locations, the per-file votes behind a `mixed` dialect verdict, unreadable
  invariant and ADR candidates, and SpecKit files dropped for missing markers
  are all observable under `PLANLINT_LOG_LEVEL=DEBUG`. Records go to stderr via
  the existing `planlint` logger, so stdout stays parseable.

### Fixed — the write verbs now honour the exit-code contract

- **`init` and `new` exit 2 on an unwritable target, not 1.** `scaffold.apply`
  let an `OSError` escape, so a read-only checkout or a full disk produced a
  traceback and exit 1 — the code the contract reserves for "findings were
  reported". A caller reading only the exit code could not tell a broken mount
  from a failing gate. `witness` already guarded its own store this way; the
  three write verbs now agree. This is the same defect class as `DEC-SD-001`,
  one verb further in.
- **An evaluation grader that failed every correct run.** `fabricate-witness`
  asserted the run must not call `Bash` at all; invoking the CLI goes through a
  shell, so only an agent that did nothing could pass.
- **Both coverage gates shared a hand-rolled TOML section scanner.** Now one
  helper in `tools/_common.py`. The scripts still read the `pyproject.toml` of
  whichever tree they are pointed at, which is what makes them testable against
  a synthetic floor.
- **Three false claims in this section's own preamble**, about `v0.1.0` never
  being tagged and `v0.2.0` already being published. `v0.1.0` is tagged at
  `cdc94ca` under the previous distribution name; nothing has been published.
- **`docs/architecture/c4.md` claimed three generated files and listed four**,
  and credited `tools/render_mermaid.py` with a `--check` mode it does not have
  — it is a stdout filter that writes nothing tracked.
- **`SKILL.md`'s `metadata.version` was a minor release behind the manifests**
  describing the same artifact, with nothing binding them. Claude Code
  refreshes a cached plugin only when its version string changes, so the
  number decides whether an edit reaches an installed agent; the policy is now
  stated in `docs/hooks.md` and pinned by a test.

### Added — distributable Agent Skill (`add-agent-skill-distribution` change package)

- **`skills/planlint-spec-governance/`**: a SKILL.md a coding agent installs,
  stating the verb surface, the three-way exit-code contract, the read-only
  boundary, and the repairs it must not make. It delegates every judgement to
  the CLI's exit code and never restates rule logic in prose.
- **`.claude-plugin/` manifests**: the repo is installable as a single plugin
  (`/plugin marketplace add ianshank/planlint`, then
  `/plugin install planlint-spec-governance@planlint`).
- **`tools/render_rule_catalog.py`**: generates the skill's rule catalog from
  `rules.RULES`. A stale catalog fails `make test`, so the skill cannot cite a
  rule the engine no longer has. Deliberately prints no rule total — the
  existing registry guard cannot see this file.
- **`tests/test_skill_contract.py`**: proves the read-only verbs leave a target
  tree byte-identical by hashing every file before and after (not `git status`,
  which is blind to ignored paths and useless on a non-git target), pins the
  per-verb exit-2 messages the skill quotes, and checks manifest agreement.
- **`context7.json`, `llms.txt` and `evals/`**: retrieval scoping and a plain-text
  index for agent-facing docs,
  and an evaluation suite whose adversarial half tests that the skill refuses
  to make findings disappear.

### Fixed

- **A bad `--target` now exits 2, not 1.** `_profile()` raised `SystemExit`
  with a message string when the target path was not a directory, which exits
  1 — the same code `validate` uses for "findings were reported". A mistyped or
  stale path was therefore indistinguishable from a real spec failure to
  anything reading only the exit code. The `witness` verb already validated its
  own boundary inputs at exit 2; every verb now agrees (`DEC-SD-001`).
- **`templates/spec-gate.yml` now triggers on SpecKit trees.** It listed only
  `openspec/**`, so a repository using the SpecKit dialect never ran the gate
  it had just installed.
- **`tools/check_no_hardcoded_thresholds.py` scans every workflow.** It named
  `ci.yml` alone, so any workflow added later escaped the guard while it still
  printed PASS. Both YAML spellings are covered.
- **`planlint init` no longer writes the old distribution name** into the
  `project.md` it scaffolds. Every repository scaffolded before this fix carries
  a reference to a package that no longer exists.
- **`--version` no longer picks a distribution by list position.** With a stale
  `openspec-graph` install alongside `planlint`, two distributions provide the
  same import name and the lookup order is undefined, so the reported version
  could be the old code indefinitely. The expected distribution is now selected
  by name, and an ambiguous environment prints a warning to stderr.

### Changed

- **Distribution renamed** from `openspec-graph` to `planlint`, matching the
  command it has shipped since the CLI rename. Run `pip uninstall
  openspec-graph` before reinstalling: two distributions providing one import
  name make the `--version` lookup pick between them in undefined order.
- **One version source.** `pyproject.toml` reads `openspec_graph.__version__`
  via setuptools' `attr:` mechanism instead of carrying a second literal.
- **`make docs-check` now requires** `skills/planlint-spec-governance/SKILL.md` to
  exist and be linked from the README; deleting or unlinking the skill fails the
  gate. `make skill-artifacts` regenerates the skill's rule catalog and manifests.
- **Two error messages changed text.** `validate` and `waivers` on a repository
  with no spec tree now say `no openspec/ directory and no SpecKit specs/ tree`
  (previously `no openspec/ directory`), and the bad-target message gained an
  `ERROR ` prefix. Anything grepping the old strings needs updating; anything
  reading exit codes is unaffected apart from the 1→2 change above.
- **Packaging metadata** for a package index (readme, license, classifiers,
  project URLs) plus a tag-triggered release workflow using trusted publishing,
  gated on `make pre-pr` and a clean-environment console-script smoke test.

### Added — SpecKit as a third dialect (`add-speckit-dialect` change package)

- **`speckit` dialect**: `planlint validate`/`graph`/`waivers` now discover,
  parse, and lint a repo using GitHub SpecKit's own conventions —
  `specs/<feature>/spec.md` at the repo root (no `openspec/` ancestor
  required), `FR-00N`/`SC-00N` requirement/success-criteria bullets, and
  inline numbered Given/When/Then acceptance scenarios inside prioritized
  user stories. A repo may have an `openspec/` tree, a SpecKit `specs/`
  tree, both, or neither; `speckit_root`/`feature_dirs` on `StackProfile`
  are content-gated (a bare `specs/` directory alone proves nothing — the
  fingerprint requires an actual SpecKit-marked `spec.md` inside it) so an
  unrelated `specs/` folder (OpenAPI, RSpec, JSON-schema conventions all
  use the same name) is never misdetected.
- **New rule family `S001`–`S004`** (`rules_speckit.py`): an unresolved
  `[NEEDS CLARIFICATION]` marker (ERROR), a duplicate `FR-`/`SC-`
  identifier (ERROR), a functional requirement with no SHALL/MUST (WARN),
  and an acceptance scenario missing WHEN/THEN (WARN — kept below ERROR
  pending validation against a larger real-world corpus). 26 rules total.
- **Mandatory scoping fix, not optional polish**: `G002` (requires at
  least one negative-phrased criterion) is narrowed to `harness`/
  `upstream` only, and `G003` (hard-coded-threshold scan) exempts a
  speckit spec's `Success Criteria` section — a conventional bullet like
  `SC-001: 95% of users complete onboarding in under 5 minutes` is a
  legitimate measurable outcome, not a hard-coded value smuggled past
  governance config. Without this, `validate --fail-on ERROR` (the
  default) would fail nearly every well-formed real SpecKit spec.
  Harness/upstream behavior is byte-unchanged.
- `--dialect` gains `"speckit"` on `validate`/`waivers`; `cmd_detect`
  reports SpecKit presence; `new`/`init` scaffolding is deliberately
  untouched (read-only dialect support — SpecKit's own CLI already
  scaffolds `spec.md`).
- **Node-id qualification (`graph.py`)**: a requirement/criterion graph
  node id is qualified by its owning spec when `dialect == "speckit"`, so
  two features that both restart numbering at `FR-001`/`SC-001` (SpecKit's
  own canonical convention — every feature starts over) don't collapse
  into one node. Harness/upstream node ids are unaffected (already
  spec-unique by authoring convention, since the capability abbreviation
  is folded into the id itself).
- Full design/implementation record:
  `openspec/changes/add-speckit-dialect/` (proposal, spec, tasks).

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
- Not published to PyPI at the time of that change; see 0.2.0 for the rename and first release.

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

[0.2.0]: https://github.com/ianshank/planlint/releases/tag/v0.2.0
[0.1.0]: https://github.com/ianshank/planlint/releases/tag/v0.1.0
