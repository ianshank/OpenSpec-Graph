# Spec: Agent Skill Distribution

> **Change:** `add-agent-skill-distribution`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT
> **Note:** every acceptance criterion below is checked off because a
> passing test verifies it; the status stays DRAFT because approval is a
> reviewer's act, not the author's.

---

## Problem Statement

A coding agent pointed at a repository has no packaged, portable way to learn
what `planlint` does or what it is allowed to do on the agent's behalf. The
verb surface, the exit-code contract, and the read-only boundary are all
inferable from `README.md` and `docs/` today, but inference is precisely the
failure mode this project exists to eliminate. An agent that guesses wrong
here does not merely produce a bad answer: it writes files into a repository
it was asked only to inspect.

**Evidence:** searching this repository for `skills/`, `.claude-plugin`,
`evals/`, and `context7.json` finds zero footprint outside
`.claude/skills/planlint-add-rule/`, which `docs/agents-skills-harness.md`
explicitly disambiguates as contributor tooling rather than shipped product.
Nothing states that `detect`, `validate`, `graph`, `rules`, and `waivers`
never write, while `init`, `new`, and `witness` do.

Three concrete defects in the CLI's own self-description were found while
grounding this design, each of which would have been copied verbatim into a
skill that trusted the existing prose. First, the exit-code contract is not
two-way but three-way, and one path breaks it outright: `_profile()` raises
`SystemExit` carrying a message string when the target path is not a
directory, which exits 1 — the same code that otherwise means "findings were
reported" — for every verb except `witness`, whose own boundary checks
already exit 2. Second, the message printed on a missing spec tree differs
between `validate`, `waivers`, and `graph`, so a skill quoting one message
would mis-recognize the other two. Third, `detect` does run one subprocess,
`git rev-parse HEAD`, so a blanket claim that the tool never shells out is
false; the true and more useful claim is that it never runs `make` and never
evaluates the target repository's own content.

A hand-maintained rule table inside the skill was considered and rejected on
this repository's own recorded history: `tests/test_rule_registry_docs.py`
exists because that drift class recurred three separate times, and a fourth
unguarded copy would reproduce it.

---

## Requirements

- R-SD-1: A distributable Agent Skill MUST live under `skills/`, and its
  SKILL.md frontmatter `name` MUST equal its own directory name.
- R-SD-2: The skill's rule catalog MUST be generated from `rules.RULES`
  rather than hand-maintained, and a stale catalog MUST fail the test suite.
- R-SD-3: Every verb the skill documents as read-only MUST leave the target
  tree byte-identical, proven by hashing every file before and after.
- R-SD-4: The exit-code messages the skill quotes MUST match what the CLI
  actually prints, per verb, mechanically verified rather than asserted.
- R-SD-5: A target path that is not a directory MUST exit 2 as a usage
  error, so that exit 1 unambiguously means findings were reported.
- R-SD-6: The plugin manifests MUST agree with the skill directory name and
  with the package version, verified rather than maintained by hand.
- R-SD-7: The existing agent-documentation drift guard MUST cover markdown
  under `skills/`, including nested frontmatter keys and references written
  relative to the document's own directory.
- R-SD-8: The CI workflow shipped as a skill asset MUST be byte-identical to
  `templates/spec-gate.yml`, and that template MUST trigger on a SpecKit
  spec tree as well as an OpenSpec one.
- R-SD-9: The distribution name and version MUST have exactly one source
  each, so a release cannot ship metadata disagreeing with the CLI.
- R-SD-10: The hard-coded-threshold guard MUST scan every workflow file, not
  only the single continuous-integration workflow.
- R-SD-11: The skill's SKILL.md MUST be a required, README-linked document.
- C-SD-1: The runtime dependency set MUST stay empty.
- C-SD-2: The skill MUST NOT be copied into `.claude/skills/`, which is
  contributor tooling for this repository rather than shipped product.
- C-SD-3: The closed CLI verb set MUST NOT grow.

---

## Decisions

- **DEC-SD-001:** `_profile()`'s not-a-directory path returns exit 2 instead
  of raising `SystemExit` with a message string. The alternative considered
  was documenting the exit-1 behaviour as-is. That was rejected because the
  skill's single most load-bearing sentence is that a nonzero exit is
  authoritative and that exit 1 means findings: an exit 1 carrying no
  findings at all makes that sentence false in the one situation an agent
  hits most often, a mistyped or stale path. The `witness` verb already
  validates its own boundary inputs at exit 2, so this aligns the two rather
  than inventing a convention.
- **DEC-SD-002:** the rule catalog is generated by a new tool rather than
  guarded by extending `tests/test_rule_registry_docs.py` to a fifth
  location. Extending the guard keeps the copy hand-written and merely
  detects drift after the fact; generating it removes the copy as an
  independent artifact. The guard's own module docstring records that this
  repository chose a test over a tool for that problem, and that precedent
  is honoured here rather than contradicted: catalog freshness is enforced
  by a test in the suite, and the tool is only the writer.
- **DEC-SD-003:** the catalog carries no total rule count.
  `tests/test_rule_registry_docs.py` matches a rule-count claim in four
  documents and matches rule rows only inside `README.md`. A generated file
  outside `README.md` is invisible to both checks, so a count printed there
  would be the one number in the repository that could drift unnoticed.
- **DEC-SD-004:** the skill ships a byte-identical copy of the CI template
  rather than referencing the repository's own `templates/` directory
  through a plugin-root variable. A plugin-root variable is undefined once
  the skill directory is copied into another agent's skills folder, which is
  the portability the Agent Skills format exists to provide. The cost is
  that the template and its copy must change together, so a test pins them.
- **DEC-SD-005:** SKILL.md frontmatter uses only single-line scalar values,
  with `metadata` as the sole nested key. The existing frontmatter parser is
  a deliberate flat line splitter, and a folded scalar would parse as the
  literal fold marker, letting a length assertion pass while measuring
  nothing. The parser gains exactly one level of nesting and no more.
- **DEC-SD-006:** the change package is gated on `validate --fail-on WARN`,
  not on ERROR alone. `graph.py` counts every non-witness finding toward
  `broken_links`, and `tools/diff_spec_graph.py` fails a pull request when
  that count rises against the base branch, so a package clean at ERROR but
  carrying one WARN turns the build red for a reason the ERROR gate never
  reports.
- **DEC-SD-007:** the skill forbids the agent from writing waivers,
  recording witnesses, editing the coverage floor, and renaming make targets
  cited by a spec. Each of these makes a finding disappear without changing
  the fact the finding described, which is the precise behaviour an
  evaluation suite must prove the skill resists rather than merely
  discourages in prose.
- **DEC-SD-008:** the skill states that no `make` is ever executed and that
  exactly one read-only `git rev-parse HEAD` may run, rather than claiming
  the tool never shells out. The narrower claim is the true one, and it is
  the one that matters to a reviewer deciding whether to point the tool at a
  repository they do not own.
- **DEC-SD-009:** distribution metadata reads the version from the package's
  own attribute rather than duplicating a literal. Two literals with no test
  binding them is the same drift class the rule registry guard exists for,
  and a release is the worst place to discover it.

---

## Acceptance Criteria

- [x] **AC-SD-1:** the skill directory carries a SKILL.md whose frontmatter
  `name` equals its parent directory name and whose description stays within
  the format's length limit. (R-SD-1)
  _Verified by:_ `pytest -k test_skill_frontmatter_name_matches_directory_name` · stage: `make test`

- [x] **AC-SD-2:** the generated rule catalog matches what the rule registry
  currently contains. (R-SD-2)
  _Verified by:_ `pytest -k test_rule_catalog_is_fresh` · stage: `make test`

- [x] **AC-SD-3 (non-success):** a stale rule catalog fails the check rather
  than being silently regenerated. (R-SD-2)
  _Verified by:_ `pytest -k test_rule_catalog_check_fails_when_stale` · stage: `make test`

- [x] **AC-SD-4 (non-success):** every read-only verb leaves the target tree
  byte-identical, with no file created, removed, or modified. (R-SD-3)
  _Verified by:_ `pytest -k test_read_only_verbs_leave_tree_byte_identical` · stage: `make test`

- [x] **AC-SD-5:** the exit-2 message quoted for each of `validate`,
  `waivers`, and `graph` is the message that verb really prints. (R-SD-4)
  _Verified by:_ `pytest -k test_exit_two_messages_match_the_documented_contract` · stage: `make test`

- [x] **AC-SD-6 (non-success):** a target path that is not a directory exits
  2 and reports no findings. (R-SD-5)
  _Verified by:_ `pytest -k test_missing_target_directory_exits_two` · stage: `make test`

- [x] **AC-SD-7:** the plugin manifests name the same skill as the skill
  directory and carry the package's own version. (R-SD-6)
  _Verified by:_ `pytest -k test_plugin_manifests_agree` · stage: `make test`

- [x] **AC-SD-8:** the documentation drift guard reads markdown under
  `skills/`, resolving references written relative to the document's own
  directory. (R-SD-7)
  _Verified by:_ `pytest -k test_skill_relative_references_resolve` · stage: `make test`

- [x] **AC-SD-9 (non-success):** a nested frontmatter value is parsed as
  itself rather than as a fold marker, so a length check measures real
  content. (R-SD-7)
  _Verified by:_ `pytest -k test_frontmatter_parses_one_nested_level` · stage: `make test`

- [x] **AC-SD-10:** the skill's CI asset is byte-identical to the template it
  was copied from. (R-SD-8)
  _Verified by:_ `pytest -k test_skill_asset_matches_template` · stage: `make test`

- [x] **AC-SD-11:** the shipped CI template triggers on a SpecKit spec tree
  as well as an OpenSpec one. (R-SD-8)
  _Verified by:_ `pytest -k test_spec_gate_template_triggers_on_speckit_trees` · stage: `make test`

- [x] **AC-SD-12:** the packaged version and the package attribute report the
  same value through one source. (R-SD-9)
  _Verified by:_ `pytest -k test_version_has_a_single_source` · stage: `make test`

- [x] **AC-SD-13 (non-success):** the threshold guard refuses a workflow file
  other than the continuous-integration one when it hard-codes a floor.
  (R-SD-10)
  _Verified by:_ `pytest -k test_threshold_guard_scans_every_workflow` · stage: `make test`

- [x] **AC-SD-14:** the skill document is listed as required and is linked
  from the README. (R-SD-11)
  _Verified by:_ `pytest -k test_required_docs_are_linked` · stage: `make test`

- [x] **AC-SD-15 (non-success):** the runtime dependency set is still empty
  after this change. (C-SD-1)
  _Verified by:_ `pytest -k test_runtime_dependencies_stay_empty` · stage: `make test`

- [x] **AC-SD-16 (non-success):** no skill is copied into the contributor
  tooling directory, which continues to hold only the rule-authoring skill.
  (C-SD-2)
  _Verified by:_ `pytest -k test_distributable_skill_is_not_copied_into_claude_skills` · stage: `make test`

- [x] **AC-SD-17 (non-success):** the closed verb set is unchanged by this
  package. (C-SD-3)
  _Verified by:_ `pytest -k test_cli_verbs_are_exactly_the_allow_list` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no invariant identifier is
cited by this spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-SD-1 through AC-SD-17 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
