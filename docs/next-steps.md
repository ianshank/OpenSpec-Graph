# Next Steps

What is intentionally **not** in scope yet, and the order to consider it. Each
item is deferred deliberately — adding it before the value is proven would be
over-engineering.

## Near term

1. ~~**Waiver audit report**~~ — shipped in CP-4 (`add-waiver-ledger-and-inv-lints`)
   as `planlint waivers --format json`: a stable-ordered ledger of every
   waived rule across the tree, with file, line, reason, and owning change.

2. ~~**Mermaid rendering**~~ — shipped in CP-GV (`add-mermaid-graph-export`)
   as `graph --format mermaid`, exactly the "thin renderer that consumes the
   JSON graph, kept out of the core projection" this item used to describe.
   **Dot/Graphviz image rendering stays rejected** (`AC-GR-6`, unrevised) —
   Mermaid is text GitHub/GitLab render natively; producing an actual image
   still needs an external engine and is still out of scope. If a consumer
   ever needs that specifically, `tools/render_mermaid.py`'s pattern (a thin
   external consumer of the saved JSON, not a core-projection change) is the
   template to follow.

3. **Rule-pack plugins** — today the 26 rules are a fixed tuple. If a target
   repo needs a custom convention (e.g. "every AC cites a JIRA ticket"), allow
   registering extra `Rule` objects via entry points. The deterministic
   contract (sorted, byte-stable JSON) must hold for plugins too.

4. **Configurable discovery lists** — `detect.py`'s `INVARIANT_SOURCES`,
   `ADR_SOURCES`, `MANIFESTS`, and the inline `governance-policy.json`
   candidate paths are fixed tuples with no override. Not a bug (nothing
   today is wrong; it's a coverage limitation of a working heuristic), but
   a repo with an invariant/ADR source or manifest convention outside the
   curated list is invisible to `detect`. Deliberately deferred out of the `add-dialect-cards` (CP-2)
   change that surfaced it: making these overridable reopens the same
   "should a hand-editable file change live-detected behavior?" question the
   `fix-init-snapshot-wording` change just resolved against (`detect` always
   re-derives fresh; a config file that overrides it reintroduces the
   stale-cached-belief problem this project exists to catch in target repos).
   Worth doing only with a clear answer to that question in hand.

4a. **Symlinked feature/change directories double-count a spec** — `detect.py`'s
   `find_spec_files()`/`find_speckit_spec_files()` both glob (`changes/*/specs/*/spec.md`,
   `specs/*/spec.md`); `Path.glob()` follows a *valid* directory symlink, so a
   `specs/002-alias -> specs/001-foo` symlink yields two distinct `Path`
   entries for the same underlying `spec.md`. Confirmed by construction
   (add-speckit-dialect PR review): `StackProfile.feature_dirs` reports 2
   features for 1 real one, and `graph.build_graph()` renders duplicate
   `FR-001`/`SC-001` nodes. Not SpecKit-specific — `find_spec_files()` has
   the identical latent behavior for `openspec/changes/`. Deferred rather
   than patched into the SpecKit PR: the fix (dedup by `Path.resolve()`
   identity, keep first-encountered logical path) is symmetric across both
   discovery functions, so it belongs in its own scoped change, not a
   dialect-specific patch that would leave the two paths asymmetric.

4b. **A `Functional Requirements`/`Success Criteria` heading at the wrong
   level silently yields zero extracted requirements/criteria, with no
   diagnostic** — `parse_speckit.py` correctly scopes its scan to the exact
   heading level SpecKit's own template uses (R-SK-30/AC-SK-49, closing a
   real over-matching bug), but the flip side is: a hand-edited spec with
   `## Functional Requirements` (H2, not the nested H3) yields `reqs: ()`
   with no warning, and still passes `S002`/`S003` cleanly (there's nothing
   to check). `G001` ("no requirements and no verifiable criteria
   recognized") only catches this if *both* are empty — a spec with working
   Success Criteria or GWT scenarios but a wrong-level FR heading passes
   silently. A candidate fix (e.g. a new WARN-level check surfacing "dialect
   is speckit but zero FR-/SC- bullets were extracted despite a `Requirements`-
   shaped section existing") needs the same spec-drafter → spec-adversary
   design pass the rest of this rule family got, not a rushed addition —
   false-positive risk against a legitimately FR-less, user-story-only draft
   spec needs real design work, not a guess.

## Medium term

5. **Sarif output** — emit `validate --format sarif` for GitHub code-scanning
   integration. The findings already carry `path`/`line`/`rule`/`severity`;
   Sarif is a projection, like the graph.

6. **Coverage trend gating** — `check_coverage_floor.py` gates against an
   absolute floor. A trend gate (branch coverage must not *decrease* vs.
   merge-base) would mirror the graph-diff pattern for coverage.

7. **CI wiring for `detect --diff`** — `detect --format json`/`--diff` (CP-2)
   is implemented as a CLI capability but has no CI job wired to it yet,
   unlike the existing `graph-diff` job it mirrors in spirit. A natural
   follow-up once the capability has proven useful in practice, not bundled
   into CP-2 itself.

## Deferred / out of scope

8. **Autonomous spec generation** — using an LLM to *author* specs is explicitly
   out of scope. `planlint` evaluates specs; it does not propose them (see
   `docs/agents-skills-harness.md`). Authoring stays a human responsibility.

9. **Docker as primary delivery** — the `Dockerfile` is a convenience runner.
   `pip install` remains the primary path; Docker is not required for local dev
   and the Makefile never depends on it (DEC-EH-001).

## Hooks & loops (deliberately not wired yet)

Each of these is a real opportunity, but is deferred until the value is proven so
it is not cargo-culted into the v0.1 surface.

10. **`make watch` dev loop** — a file-watcher that re-runs `make validate` (or
    `make test -- -k spec`) on every spec/source change. Worth adding only with a
    dependency-free watcher (stdlib `asyncio` + `os.stat` polling, or `watchdog`
    as an optional extra). Today the pre-commit hook already runs validate on
    commit, which covers the main need.

11. **Scheduled self-validation cron** — a scheduled job that runs `planlint
    validate --fail-on ERROR` + `make security` against `main` to catch spec/rules
    drift introduced by dependency or tooling bumps. Only justified once the repo
    is consumed by more than one team; for a single-consumer v0.1 tool the PR CI
    gate already enforces this on every change.

12. **Pre-push hook** — `make pre-pr` is the one-command gate; a `.git/hooks/
    pre-push` that calls it would catch a broken push before CI. Documented as
    optional in `docs/hooks.md` rather than forced, because the full suite
    (coverage included) is slower than the six commit-time hooks (lint,
    typecheck, security, validate, docs-check, thresholds) and most pushes
    are already covered by pre-commit + CI.

18. **`E501` is configured but not enforced** — `[tool.ruff] line-length = 100`
    has always been set, but ruff's `select` was never set either, so the
    default `E4/E7/E9/F` applied and the `E5` group (line length) was never
    on. Turning it on today reports **100 violations**: 33 in
    `openspec_graph/` and `tools/`, the rest in tests, with a median overage
    of six characters and a maximum of 214. The `select` list added alongside
    this note enables every family that was already at or near zero, and
    names `E501` as the one deliberate omission. The work owed is the
    rewrap, as its own change: bundling 100 reflowed lines across a dozen
    files into an unrelated branch buries whatever else that branch did.

19. **`tools/` is linted and typechecked but measured by nothing** —
    `[tool.coverage.run] source` is `["openspec_graph"]`, so the gate scripts
    that enforce every other gate have no coverage number of their own. Adding
    `--cov=tools` today reports 88.3% line / 84.6% branch overall, which fails
    the 90% floor -- but the shortfall is mostly *measurement*, not absence:
    several tools are exercised only through `subprocess.run` calls that do
    not inject `COVERAGE_PROCESS_START`, so their lines are invisible even
    though tests run them. `tests/support.py`'s `run_cli` already does this
    correctly for the CLI; the fix is a sibling helper for tool invocations,
    after which the real gaps (`_common.write_or_check`'s check-mode branches,
    `check_secrets`'s gitleaks-present path) can be judged on their merits.
    Worth doing before the floor is ever raised, since today the number does
    not describe what it claims to.

## Skills / agents

13. **Rules as reusable skills** — the 26 rules already are the reusable
    "skills" and the evaluator is the deterministic harness (see
    `docs/agents-skills-harness.md`). The future extension point for composing
    rule packs across repos is item 3 (entry-point `Rule` registration). No
    autonomous agent layer is planned: the harness evaluates, it never proposes
    or acts (INV-16 — the evaluator proposes nothing).

14. **The distributable Agent Skill is a caller, not an agent layer** — since
    `add-agent-skill-distribution`, `skills/planlint-spec-governance/` tells an
    external agent how to *invoke* this CLI. That does not contradict item 13:
    the skill contains no rule logic, its catalog is generated from the
    registry, and the agent reading it is somebody else's, running outside this
    process. The harness still only disposes.

15. **PEP 639 licence metadata** — `pyproject.toml` still uses the
    `license = { text = ... }` table form, which setuptools 77 deprecated in
    favour of an SPDX string plus a `license-files` glob, with removal
    announced. The migration is owed, not optional: a build months from now can
    warn or fail on a form that was correct when written. It was attempted and
    backed out because the SPDX form makes setuptools require
    `packaging>=24.2` at build time, which could not be verified in the
    environment available (a distro-managed `packaging` 24.0 that cannot be
    upgraded). Do it as its own change, with a proven clean-environment build,
    and raise `[build-system] requires` to `setuptools>=77` in the same commit.
    `Dockerfile` already copies `LICENSE` so the `license-files` glob will not
    break the image build when it lands.

16. **CI wiring for the eval suite** — the cases under `evals/` have no job
    running them. `claude plugin eval` needs a plugin runtime CI does not have,
    and the adversarial half is non-deterministic by nature, so it stays a
    manual pre-release check rather than a gate. `tests/test_agent_artifacts.py`
    validates the suite's *structure* deterministically, which is the part that
    can be gated. Revisit if a headless runner appears.

17. **Deliberately not done for the skill (yet)** — a published tool wrapper
    for programmatic multi-agent frameworks (a subprocess shim with its own
    release cadence, shipping untested from here); a hosted evaluation dataset
    (the suite under `evals/` is the source, an export is mechanical); and any
    skill capability that would let an agent write a waiver, record a witness,
    or edit a threshold. The last one is not a roadmap item but a permanent
    non-goal — those are exactly the moves the adversarial evaluation cases
    exist to prove the skill refuses.
