# Next Steps

What is intentionally **not** in scope yet, and the order to consider it. Each
item is deferred deliberately — adding it before the value is proven would be
over-engineering.

## Near term

1. **Waiver audit report** — `planlint validate` already downgrades waived
   rules to INFO and keeps them visible. A `planlint waivers` verb that lists
   every active waiver across the tree would make suppressions reviewable at a
   glance. Low effort; pure read of existing parse output.

2. **Dot/Graphviz rendering** — `graph --format dot` is currently rejected
   (rendering is out of scope). If a consumer needs it, add a thin renderer that
   consumes the JSON graph; keep it out of the core projection so
   `broken_links` stays a pure finding count.

3. **Rule-pack plugins** — today the 18 rules are a fixed tuple. If a target
   repo needs a custom convention (e.g. "every AC cites a JIRA ticket"), allow
   registering extra `Rule` objects via entry points. The deterministic
   contract (sorted, byte-stable JSON) must hold for plugins too.

4. **Configurable discovery lists** — `detect.py`'s `INVARIANT_SOURCES`,
   `MANIFESTS`, and the inline `governance-policy.json` candidate paths are
   fixed tuples with no override. Not a bug (nothing today is wrong; it's a
   coverage limitation of a working heuristic), but a repo with an invariant
   source or manifest convention outside the curated list is invisible to
   `detect`. Deliberately deferred out of the `add-dialect-cards` (CP-2)
   change that surfaced it: making these overridable reopens the same
   "should a hand-editable file change live-detected behavior?" question the
   `fix-init-snapshot-wording` change just resolved against (`detect` always
   re-derives fresh; a config file that overrides it reintroduces the
   stale-cached-belief problem this project exists to catch in target repos).
   Worth doing only with a clear answer to that question in hand.

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
    (coverage included) is slower than the commit-time lint+typecheck+validate
    hook and most pushes are already covered by pre-commit + CI.

## Skills / agents

13. **Rules as reusable skills** — the 18 rules already are the reusable
    "skills" and the evaluator is the deterministic harness (see
    `docs/agents-skills-harness.md`). The future extension point for composing
    rule packs across repos is item 3 (entry-point `Rule` registration). No
    autonomous agent layer is planned: the harness evaluates, it never proposes
    or acts (INV-16 — the evaluator proposes nothing).
