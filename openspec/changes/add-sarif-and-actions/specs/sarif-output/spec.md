# Spec: SARIF Output

> **Change:** `add-sarif-and-actions`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

`validate`'s findings reach an adopter in exactly two shapes: sorted plain
text on stdout, and a JSON envelope both shipped CI recipes redirect into a
build artifact nobody opens. Neither appears in the pull request the
organization already reviews. GitHub code scanning consumes SARIF 2.1.0 and
renders each result inline on the diff, which is where a finding about a
lying spec belongs.

**Evidence:** `openspec_graph/cli.py::cmd_validate` (`cli.py:417-452`) has one
machine-readable branch — `--json` — and both
`.github/workflows/ci.yml:62-72` and the adopter-facing
`templates/spec-gate.yml:44-52` invoke it as
`validate --fail-on WARN --json > spec-findings.json || true`, then upload
the file with `actions/upload-artifact@v4`. The `|| true` makes the payload
deliberately non-blocking; nothing surfaces it to a reviewer.
`docs/differentiation-roadmap.md`'s `CP-6` section commits the capability and
records its own cutline — never drop a finding to satisfy a schema.

Two facts about the current tree constrain the mapping, and both were found
by grounding the sketch against the code rather than by reading the sketch:

- **No finding produced through the CLI carries a line number.**
  `rules.evaluate()` (`rules.py:86-93`) and `rules.evaluate_tree()`
  (`rules.py:118-139`) are the only `Finding(...)` construction sites in the
  package; neither passes `line=`, and `Finding.line` defaults to `0`
  (`rule_types.py:46`). SARIF's `region.startLine` is `>= 1`, so `0` has no
  valid representation and must be omitted rather than clamped.
- **`tests/test_adopter_urls.py` does not discover `.github/`.**
  `_adopter_files()` (`test_adopter_urls.py:147-155`) globs `*.md`,
  `docs/**/*.md`, `skills/**/*.md`, `skills/**/*.yml`, `templates/*.yml`, and
  `Dockerfile`. A composite action's pinned install line is outside that
  corpus today, so the guard the planning pass relied on does not yet cover
  the artifact this change adds.

---

## Requirements

- R-SA-1: `validate --format sarif` MUST print a SARIF 2.1.0 log to stdout as
  JSON, carrying at minimum `$schema`, `version` (exactly `"2.1.0"`), and a
  `runs` array of exactly one run containing `tool.driver` and `results`.
- R-SA-2: `validate` MUST accept `--format {text,json,sarif}`, defaulting to
  `text`. `--json` MUST be preserved and MUST remain an exact alias of
  `--format json`: byte-identical stdout, identical exit codes, no
  deprecation line on either stream.
- R-SA-3: Passing `--json` together with `--format sarif` MUST be a usage
  error — exit code 2, one message on **stderr** naming both flags, and
  **nothing** on stdout. `--json` together with the redundant
  `--format json` MUST be accepted, since the two express the same request.
- R-SA-4: The SARIF projection MUST consume the same already-computed,
  already-ordered findings list `cmd_validate` builds for the text and
  `--json` branches. It MUST NOT call `rules.evaluate()`,
  `rules.evaluate_tree()`, or re-parse any spec. One traversal, one source of
  truth.
- R-SA-5: Severity MUST map `ERROR` → `"error"`, `WARN` → `"warning"`,
  `INFO` → `"note"`. An `ERROR` finding MUST NOT be emitted at any SARIF
  level below `"error"`. An unrecognized severity MUST map to `"error"` and
  MUST NOT map to `"none"`.
- R-SA-6: `results[].locations[].physicalLocation.artifactLocation.uri` MUST
  be the finding's repository-relative POSIX path as
  `Finding.as_dict(root)` already renders it (via
  `detect.to_posix_relative`) — never absolute, never native-separator — and
  `uriBaseId` MUST be `"%SRCROOT%"`.
- R-SA-7: `region.startLine` MUST be emitted only when the finding's `line`
  is `>= 1`. A `line` of `0` MUST produce no `region` key at all; it MUST NOT
  be clamped to `1`, defaulted, or otherwise represented as a location on a
  line the finding is not about.
- R-SA-8: A finding whose `path` is `None` MUST still be emitted as a result,
  with an empty `locations` array. It MUST NOT be dropped, MUST NOT be
  represented with a `null` or empty-string `uri`, and MUST NOT raise.
- R-SA-9: `runs[].tool.driver` MUST carry `name` (`"planlint"`), `version`
  (the value `cli._package_version()` returns), `informationUri` (the
  project homepage), and `rules` — one entry per registered rule, built from
  `rules.rule_table()`, in that table's order, each with `id`,
  `shortDescription.text` equal to the rule's existing `summary`, and
  `defaultConfiguration.level` equal to that rule's mapped severity.
- R-SA-10: Every result MUST carry `ruleId` and `ruleIndex`, `ruleId` MUST
  appear as an `id` in `tool.driver.rules`, and `ruleIndex` MUST be the
  index of that entry. Every result MUST carry a non-empty `message.text`.
- R-SA-11: Results MUST be ordered by `cli._sort_key` — the same key the text
  renderer and `--json` already use — so all three renderings of one run
  agree on order.
- R-SA-12: Two consecutive `validate --format sarif` runs against an
  unchanged tree MUST produce byte-identical stdout.
- R-SA-13: `openspec_graph/sarif.py` MUST be pure and stdlib-only, perform no
  I/O, import no other module in this package, and accept only plain data
  (already-serialized finding dicts, the rule table, and the tool version
  string) — never a `Path`, a `StackProfile`, or a `Finding` object.
- R-SA-14: `validate --format sarif` MUST return the same exit code
  `validate --json` returns for the same run: `1` when findings at or above
  `--fail-on` exist, `0` otherwise.
- R-SA-15: `validate --format sarif` MUST NOT create, modify, or remove any
  file or directory in the target tree, and MUST NOT open a network
  connection.
- R-SA-16: `.github/actions/planlint/action.yml` MUST be a composite action
  that, in order, sets up Python, installs `planlint` pinned to a version
  range, runs `detect`, runs `validate --format sarif` redirected to a file,
  and uploads that file with `github/codeql-action/upload-sarif`. The upload
  step MUST run even when the validate step failed, so a red gate still
  produces annotations.
- R-SA-17: `tests/test_adopter_urls.py::_adopter_files()` MUST be widened to
  discover `.github/actions/**/*.yml` and the repository-root
  `.pre-commit-hooks.yaml`, so the composite action's pinned install line is
  covered by the existing install-drift guards rather than assumed to be.
- R-SA-18: A `.pre-commit-hooks.yaml` MUST exist at the repository root
  declaring at least one hook that invokes `planlint validate`. It MUST NOT
  redefine, rename, or otherwise disturb this repository's own
  contributor-facing `.pre-commit-config.yaml`.
- C-SA-1: This change MUST NOT alter `validate --json`'s payload,
  `rules.FINDINGS_SCHEMA_VERSION`, or any of
  `tests/test_decomposition.py::_EXPECTED_HASHES`.
- C-SA-2: This change MUST NOT add, remove, or rename a field on the `Rule`
  dataclass, and MUST NOT change `rule_table()`'s returned shape.
- C-SA-3: This change MUST NOT add a rule, a rule family, or a CLI verb. The
  rule registry MUST still hold exactly the rules it holds today, and
  `tests/test_cli_surface.py::ALLOWED_VERBS` MUST be unchanged.
- C-SA-4: This change MUST NOT add a runtime or test dependency, including a
  YAML parser.
- C-SA-5: `graph --format`'s choices MUST be unchanged, and `--format dot`'s
  existing rejection (`AC-GR-6`) MUST be unrevised. `sarif` is a `validate`
  format only.

---

## Decisions

- **DEC-SA-001:** `--json` is kept as an alias, not deprecated and not
  removed. Three shipped surfaces pass it — `.github/workflows/ci.yml`,
  `templates/spec-gate.yml` and its byte-identical twin inside the
  distributed skill, and `SKILL.md`'s own structured-output guidance — and
  `tests/test_enterprise.py::test_cli_verbs_backward_compatible`
  parametrizes it as part of the surface `AC-EH-7` promised to keep. A
  deprecation line would also be a second, unrelated migration landing in
  the same release as a new format, which `DEC-FE-003` already argued
  against for the envelope's key names. The alias costs one line and breaks
  nobody.
- **DEC-SA-002:** `--json` plus `--format sarif` is exit 2, not a precedence
  rule. Either precedence order is defensible and neither is guessable, so
  a CI author who wrote both would get one of two formats silently and
  discover it from a code-scanning upload that mysteriously contains a
  findings envelope. `witness`'s own boundary validation set the precedent:
  reject at the CLI edge, before any work, with a message that names the
  conflict (`AC-WM-12..18`). `--json --format json` is *accepted* rather
  than rejected on the same principle — it is redundant, not contradictory,
  and rejecting it would break a caller who added `--format json` for
  clarity.
- **DEC-SA-003:** a `line` of `0` omits `region` entirely; it is never
  clamped to `1`. SARIF's `startLine` minimum is `1`, so `0` cannot be
  represented, and the two ways to "handle" that are to omit the region or
  to invent one. Clamping would put an annotation on the first line of a
  real file, in a real pull request, pointing at content the finding is not
  about — a wrong location is worse than no location, because a reviewer
  cannot tell it is wrong. This matters more than it looks: **every** finding
  the CLI produces today has `line == 0` (`rules.py:86-93`,
  `rules.py:118-139` pass no `line=`), so under a clamping implementation
  *every* annotation would be wrong. The file-level location is still
  emitted, which is what GitHub needs to attach the alert to the right file.
- **DEC-SA-004:** a finding with no `path` is emitted with `locations: []`,
  not dropped and not given a synthetic location. The roadmap's own risk
  table fixes the cutline — "map down to the supported subset rather than
  dropping findings; every ERROR must survive the round-trip" — and losing a
  finding to make a schema happy is the precise failure this spec forbids
  (`AC-SA-4`). An empty array is valid SARIF and is honest: it says "no
  location was computed," where a synthetic `uri` would assert a file. This
  state is unreachable through any CLI path today (`DEC-WL-004`: G006/G009
  set `path` to the declaring source, every other rule to the spec's own
  path), so its test constructs the input directly rather than driving the
  CLI — the same technique `AC-FE-5` uses for the same reason, so the
  criterion cannot pass vacuously on an empty set. If GitHub's ingestion is
  later observed to reject locationless results, the fallback is to attach
  the repository-root artifact location, never to drop the result and never
  to invent a line.
- **DEC-SA-005:** `tool.driver.rules` is built from `rules.rule_table()`,
  reusing each rule's existing `summary` for `shortDescription.text`. A
  richer `description` field on the `Rule` dataclass was rejected:
  `tests/test_decomposition.py::_EXPECTED_HASHES["rules"]` pins a golden
  hash of `rules --json`, whose rows come from `rule_table()`, so widening
  the rule shape re-pins that hash — a hash whose comment block already
  records four re-pins and their reasons — to add prose no rule author has
  written yet. `tools/render_rule_catalog.py` already renders the same four
  fields into the skill's catalog and deliberately adds none; a third
  projection of the registry has no standing to demand a fifth.
- **DEC-SA-006:** the full registry is emitted in `driver.rules`, not only
  the rules that fired. GitHub attaches alert metadata by `ruleId` against
  the driver's rule set, so a rule that fires for the first time in a later
  run would otherwise arrive with no name or description. It also makes the
  driver block a function of the build rather than of the target repository,
  which is what keeps `R-SA-12`'s byte-stability easy to hold. `W001`/`W002`
  appear even though they are not evaluated without `--require-witness` —
  the same choice `rules --json` already makes for discoverability.
- **DEC-SA-007:** `sarif.py` takes already-serialized finding dicts
  (`Finding.as_dict(root)`'s output) rather than `Finding` objects. Path
  relativization then happens exactly once, inside the serializer that
  already owns it (`DEC-FE-001`), and `sarif.py` needs no `Path`, no
  `detect` import, and no knowledge of the target root — which is what lets
  it hold `mermaid.py`'s and `dialect_card.py`'s zero-intra-package-import
  posture instead of merely claiming to be pure. The cost is that `sarif.py`
  depends on the envelope's finding-dict keys; that dependency is real
  either way, and stating it as a dict contract makes it testable without a
  filesystem.
- **DEC-SA-008:** the severity map fails *upward*. An unrecognized severity
  maps to `"error"`, never to SARIF's `"none"`. `"none"` is invisible in
  code scanning, so a mapping bug would silently delete findings from the
  pull request while every exit code stayed correct — the hardest possible
  failure to notice. Mapping up produces a loud, wrong-looking alert
  instead, which someone fixes. The map is a module-level constant with an
  explicit default, not a `dict.get(sev, "none")` at a call site.
- **DEC-SA-009:** the composite action's pinned install line is guarded by
  widening `tests/test_adopter_urls.py::_adopter_files()`, not by assuming
  the existing corpus covers it. It does not: that module's globs stop at
  `templates/*.yml` and the skill tree. Its own docstring names the incident
  this matters for — "the project was renamed … and eight places kept
  printing an install command for a name that no longer existed" — and its
  stated design rule is that files are *discovered, not listed*, precisely
  so a ninth place cannot drift unnoticed. Adding a tenth place while
  leaving it outside the glob would reproduce the original bug in the file
  written to prevent it.
- **DEC-SA-010:** `.pre-commit-hooks.yaml` (new, adopter-facing) and
  `.pre-commit-config.yaml` (existing, contributor-facing) are two different
  files with two different audiences, and this change adds the first without
  touching the second. The existing config declares `local` hooks that
  invoke this repository's own `make` targets and requires
  `pip install -e ".[dev]"`; the new hooks file is what a *foreign*
  repository's config points at to run `planlint validate` against itself.
  Recorded explicitly because the filenames differ by one word and a
  reviewer's first question will be whether one supersedes the other. It
  does not.
- **DEC-SA-011:** `--format sarif` keeps `validate`'s exit-code contract —
  `1` when blocking findings exist. Exiting `0` and "letting the annotations
  speak" was rejected: the exit code *is* the gate, and the whole product
  claim is that a stranger's clone can be failed with one. A repository that
  wants annotations without a red X sets `--fail-on` or the action step's
  own `continue-on-error`, both of which are explicit and visible in the
  workflow file.
- **DEC-SA-012:** `planlint` itself never talks to GitHub. Upload is
  `github/codeql-action/upload-sarif`'s job inside the composite action. The
  roadmap's "SARIF + GitHub Check" phrasing could be read as an API client,
  but adding one would mean a token, an HTTP dependency, and a network call
  inside a tool whose headline guarantee is that it only reads the tree it
  is pointed at (`AC-SD-4`, `AC-DC-3`). The Check Run appears either way;
  only one of the two designs keeps the guarantee.
- **DEC-SA-013:** the new YAML artifacts are checked as text, not parsed. No
  test in this repository imports `yaml`, and `C-SA-4` forbids adding the
  dependency to gain it. `tests/test_adopter_urls.py` already argues the
  general case — "these are text checks, deliberately" — and
  `tools/check_thresholds.py` already reads workflow YAML the same way. The
  checks are correspondingly narrow and stated as such: the install line
  names the published distribution, the required steps appear in order, and
  the hooks file declares a `planlint validate` entry.

---

## Acceptance Criteria

- [ ] **AC-SA-1:** `validate --format sarif` on a fixture repo with findings
  emits parseable JSON whose required 2.1.0 keys are all present and
  correct: `$schema`, `version == "2.1.0"`, exactly one `runs` entry,
  `runs[0].tool.driver.name == "planlint"`, a non-empty
  `runs[0].tool.driver.rules`, and a `runs[0].results` array. Asserted
  structurally against the required key set — no schema is fetched, since
  the suite has no network. (R-SA-1, R-SA-9)
  _Verified by:_ `pytest -k test_sarif_output_has_the_required_2_1_0_shape` · stage: `make test` (test not yet written)

- [ ] **AC-SA-2:** For one run over a fixture repo producing findings in more
  than one spec file — asserted non-empty first, so the comparison cannot
  pass vacuously — the multiset of `(rule, path, line)` triples in
  `--format sarif` equals the multiset in `--format json`. (R-SA-4, R-SA-8)
  _Verified by:_ `pytest -k test_sarif_and_json_report_the_same_finding_multiset` · stage: `make test` (test not yet written)

- [ ] **AC-SA-3:** An `ERROR` finding is emitted at SARIF level `"error"`, a
  `WARN` at `"warning"`, an `INFO` at `"note"`; the severity map covers every
  severity constant `rule_types` defines, and an unrecognized severity maps
  to `"error"`, never `"none"`. (R-SA-5, DEC-SA-008)
  _Verified by:_ `pytest -k "test_error_severity_maps_to_sarif_error or test_severity_map_covers_every_severity or test_an_unknown_severity_maps_up_not_to_none"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-4 (non-success):** A finding whose `path` is `None` is emitted
  as a result with an empty `locations` array — never dropped, never
  rendered with a `null` or empty `uri`, never raising. The input is
  constructed directly rather than driven through the CLI, because no CLI
  path produces a pathless finding today, and a criterion exercised against
  an empty set proves nothing. (R-SA-8, DEC-SA-004)
  _Verified by:_ `pytest -k "test_a_finding_with_no_path_is_emitted_without_a_location or test_no_finding_is_ever_dropped_from_the_sarif_log"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-5 (non-success):** A finding with `line == 0` produces a result
  with a `physicalLocation` and **no** `region` key — not
  `region.startLine == 1`, not `startLine == 0`. A finding carrying a real
  line produces `region.startLine` equal to that line. (R-SA-7, DEC-SA-003)
  _Verified by:_ `pytest -k "test_a_line_of_zero_emits_no_region or test_a_real_line_emits_a_start_line"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-6:** Every `artifactLocation.uri` in a real run is a
  forward-slash, repository-relative string — no leading separator, no drive
  letter, no backslash, no copy of the checkout path — `uriBaseId` is
  `"%SRCROOT%"`, and joining the run's target to the `uri` resolves to the
  file the finding is about. (R-SA-6)
  _Verified by:_ `pytest -k "test_artifact_uri_is_repository_relative_posix or test_artifact_location_carries_the_srcroot_base_id"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-7:** The sequence of `(path, rule)` pairs in `results` equals
  the sequence `--format json` reports and the sequence the text renderer
  prints, for the same run. (R-SA-11)
  _Verified by:_ `pytest -k test_sarif_results_are_ordered_like_the_text_renderer` · stage: `make test` (test not yet written)

- [ ] **AC-SA-8:** `tool.driver.rules` has one entry per row of
  `rules.rule_table()`, in that order, with `id` and
  `shortDescription.text` equal to the row's `id` and `summary` and
  `defaultConfiguration.level` equal to the mapped severity; every
  `results[].ruleId` resolves to one of those entries and its `ruleIndex`
  selects that same entry. (R-SA-9, R-SA-10, DEC-SA-005, DEC-SA-006)
  _Verified by:_ `pytest -k "test_driver_rules_mirror_the_rule_table or test_every_result_rule_index_resolves_to_its_rule_id"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-9 (non-success):** `--json` is unchanged. Its stdout is
  byte-identical to `--format json`'s, both exit codes match, the golden
  hashes for `validate`, `graph`, and `rules` are unmodified, and the `Rule`
  dataclass has gained no field. (R-SA-2, C-SA-1, C-SA-2, DEC-SA-001,
  DEC-SA-005)
  _Verified by:_ `pytest -k "test_json_flag_is_an_exact_alias_of_format_json or test_output_byte_identical or test_cli_verbs_backward_compatible"` · stage: `make test` (`test_json_flag_is_an_exact_alias_of_format_json` not yet written; the other two exist)

- [ ] **AC-SA-10 (non-success):** `validate --json --format sarif` exits 2,
  prints one message naming both flags to stderr, and prints nothing at all
  to stdout — a half-written SARIF log on stdout beside a usage error would
  be worse than either. `validate --json --format json` is accepted and
  behaves as `--json`. (R-SA-3, DEC-SA-002)
  _Verified by:_ `pytest -k "test_json_with_format_sarif_is_a_usage_error or test_json_with_format_json_is_accepted"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-11:** Two consecutive `validate --format sarif` runs over an
  unchanged tree produce byte-identical stdout. (R-SA-12)
  _Verified by:_ `pytest -k test_sarif_output_is_byte_stable_across_runs` · stage: `make test` (test not yet written)

- [ ] **AC-SA-12 (non-success):** `validate --format sarif` writes nothing to
  the target tree — no created, removed, or modified file, and no created
  directory. Enforced by adding the invocation to
  `tests/test_skill_contract.py::READ_ONLY_INVOCATIONS`, whose existing
  whole-tree digest comparison (files *and* directories, dotfiles walked)
  then covers it, and whose exit-code guard keeps the assertion from passing
  because the command refused to run. (R-SA-15)
  _Verified by:_ `pytest -k test_read_only_verbs_leave_tree_byte_identical` · stage: `make test` (test exists; the `READ_ONLY_INVOCATIONS` entry does not)

- [ ] **AC-SA-13:** `openspec_graph/sarif.py` imports only the standard
  library, imports no module from this package, and is listed in
  `tests/test_decomposition.py::_NEW_MODULES` so both properties are checked
  mechanically rather than by convention. (R-SA-13, C-SA-4)
  _Verified by:_ `pytest -k "test_new_modules_stdlib_only or test_import_boundary_discipline"` · stage: `make test` (tests exist; the `_NEW_MODULES` entry does not)

- [ ] **AC-SA-14:** `.github/actions/planlint/action.yml` exists, declares a
  composite action, and contains — in order — a Python setup step, a pinned
  `planlint` install, a `detect` step, a `validate --format sarif` step
  redirecting to a file, and an `upload-sarif` step that runs even when
  validate failed. Its install line names the published distribution, and it
  is discovered by the widened adopter corpus rather than exempt from it.
  (R-SA-16, R-SA-17, DEC-SA-009)
  _Verified by:_ `pytest -k "test_the_composite_action_declares_the_expected_steps or test_the_adopter_corpus_includes_the_composite_action or test_install_lines_spell_this_project_the_way_it_is_published"` · stage: `make test` (the first two are not yet written; `test_install_lines_spell_this_project_the_way_it_is_published` exists and becomes load-bearing once the corpus is widened)

- [ ] **AC-SA-15:** `.pre-commit-hooks.yaml` exists at the repository root and
  declares at least one hook whose entry invokes `planlint validate`; the
  existing `.pre-commit-config.yaml` still declares its six local `make`
  hooks unchanged, and no hook id is defined in both files. (R-SA-18,
  DEC-SA-010)
  _Verified by:_ `pytest -k "test_pre_commit_hooks_file_declares_a_validate_hook or test_the_two_pre_commit_files_do_not_collide"` · stage: `make test` (test not yet written)

- [ ] **AC-SA-16:** No rule, rule family, or CLI verb was added; the rule
  registry holds exactly the rules it held before this change, and every
  document that states a rule count still agrees with `rules.RULES`.
  (C-SA-3)
  _Verified by:_ `pytest -k "test_cli_verbs_are_exactly_the_allow_list or test_total_rule_count_matches_every_prose_claim"` · stage: `make test` (selectors must be confirmed against the real names in `tests/test_cli_surface.py` and `tests/test_rule_registry_docs.py` during implementation; if either differs, cite the real one rather than adding a duplicate test)

- [ ] **AC-SA-17:** `validate --format sarif` returns the same exit code as
  the text and JSON runs of the same repository, at the same `--fail-on`. The
  format decides how findings are rendered, never whether the gate passes; a
  job that switched to SARIF for annotations must not also, silently, stop
  failing. The test covers both a failing and a clean fixture, so the equality
  is not three zeroes agreeing with each other. (R-SA-14)
  _Verified by:_ `pytest -k test_sarif_returns_the_same_exit_code_as_the_text_run` · stage: `make test`

- [ ] **AC-SA-18 (non-success):** `graph --format`'s choices are unchanged by
  this change, and `--format dot` still exits 2 emitting nothing on stdout —
  `dot` remains an accepted choice refused at runtime, so the message can
  explain that image rendering is out of scope rather than argparse saying
  only "invalid choice". Adding a format to `validate` must not leak into a
  sibling verb. (C-SA-5)
  _Verified by:_ `pytest -k test_graph_format_choices_are_unchanged` · stage: `make test`

- [ ] **AC-SA-19:** `README.md`, `SKILL.md`, and `CHANGELOG.md` describe
  `validate --format sarif`, the `--json` alias, and the composite action;
  no document still claims `--json` is the only machine-readable output.
  (R-SA-1, R-SA-2, R-SA-16)
  _Verified by:_ manual review · stage: `make docs-check`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-SA-1..18 |
| Core | `make ci` | AC-SA-1..18, plus lint and this repo's own `planlint validate` over this package |
| Docs | `make docs-check` | AC-SA-19 (manual review; no automated content check covers README/SKILL prose) |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
