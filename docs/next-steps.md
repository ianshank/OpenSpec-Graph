# Next Steps

What is intentionally **not** in scope yet, and the order to consider it. Each
item is deferred deliberately — adding it before the value is proven would be
over-engineering.

## Near term

1. **Waiver audit report** — `specgraph validate` already downgrades waived
   rules to INFO and keeps them visible. A `specgraph waivers` verb that lists
   every active waiver across the tree would make suppressions reviewable at a
   glance. Low effort; pure read of existing parse output.

2. **Dot/Graphviz rendering** — `graph --format dot` is currently rejected
   (rendering is out of scope). If a consumer needs it, add a thin renderer that
   consumes the JSON graph; keep it out of the core projection so
   `broken_links` stays a pure finding count.

3. **Rule-pack plugins** — today the 16 rules are a fixed tuple. If a target
   repo needs a custom convention (e.g. "every AC cites a JIRA ticket"), allow
   registering extra `Rule` objects via entry points. The deterministic
   contract (sorted, byte-stable JSON) must hold for plugins too.

## Medium term

4. **Sarif output** — emit `validate --format sarif` for GitHub code-scanning
   integration. The findings already carry `path`/`line`/`rule`/`severity`;
   Sarif is a projection, like the graph.

5. **Coverage trend gating** — `check_coverage_floor.py` gates against an
   absolute floor. A trend gate (branch coverage must not *decrease* vs.
   merge-base) would mirror the graph-diff pattern for coverage.

## Deferred / out of scope

6. **Autonomous spec generation** — using an LLM to *author* specs is explicitly
   out of scope. `specgraph` evaluates specs; it does not propose them (see
   `docs/agents-skills-harness.md`). Authoring stays a human responsibility.

7. **Docker as primary delivery** — the `Dockerfile` is a convenience runner.
   `pip install` remains the primary path; Docker is not required for local dev
   and the Makefile never depends on it (DEC-EH-001).
