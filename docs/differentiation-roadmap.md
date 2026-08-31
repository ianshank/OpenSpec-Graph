# OpenSpec-Graph Differentiation — Implementation Plan

> Planning artifact. Not implementation. Not part of PR #4 (`decompose-god-files`).
> If committed, goes on a separate doc-only branch.

## Wedge

**One sentence, repeated until it is true in the README:** the CI gate that
fails when a spec cites a gate this repo does not have — and proves the gate
actually ran.

The losing move is becoming "yet another spec graph." The winning move is
being the only tool you can point at a stranger's clone and say, with an exit
code, whether the plan is lying. The moment this becomes a place people *write*
specs, it is in a feature race with 60k-star tools and it loses.

The structural difference to put on the README in one table:

| | openspec `validate` / Spec Kit | **planlint** |
|---|---|---|
| What it checks | document shape | spec ↔ repo machinery agreement |
| Graph edges | proposal→tasks | requirement→criterion→make target→config number→declared INV |
| "make regression" | mentioned in prose | exists in the Makefile, and optionally a witness proves it ran |
| Thresholds | prose claim | read structurally from `fail_under` / `coverage.lines` |
| Invariants | cited INV exists | cited INV exists **and** declared INV is cited (bidirectional) |
| Target repo | owned, templated | foreign, read-only, any house style |

## Non-Goals (what this product refuses to be)

- Not a queryable spec database (SpecGraph already is one).
- Not a propose/apply chat workflow (OpenSpec / Spec Kit).
- Not a generic markdown quality score.
- Not a constitution store, authoring funnel, or MCP workbench.
- Not a replacement for `openspec validate` — a gate *under* it.
- No hard-coded house style; everything is detected from the target repo.

---

## Release Sequence

Four releases. Each is a defensible position on its own; later releases deepen
the moat rather than rescuing an unfinished v1.

### v1 — The Moat (sharpen the existing tool)

The tool already lints. v1 makes the lint *un-copyable*: it reads the repo's
real machinery as structure, emits a dialect card that drifts loudly, and
proves the CLI is safe to point at a repo you do not own.

### v2 — Proof, Not Citation

Witness mode. A spec's `_Verified by:` stops being fan fiction — it must cite a
CI-uploaded witness stub (target, exit code, coverage number, commit SHA).
This is the line competitors cannot cross without becoming CI infrastructure.

### v3 — Portfolio Nervous System

One tool across many house styles. Dialect cards as a diffable CI artifact, an
org-wide scan that produces an architecture/governance table, and a waiver
ledger auditors will actually buy.

### v4 — Distribution + Agent Eval

SARIF + GitHub Check (live in the PR the org already has), a 5-minute
time-to-first-red-X composite Action, and a public 20-spec agent-failure
corpus with a published catch-rate. Category claims die; catch-rate claims sell.

---

## Candidate Change Packages

Eight packages. Not scaffolded yet — each is a sketch with acceptance criteria
(including a non-success criterion, per the repo's own G002 rule — see
`tests/fixtures/good_harness.md` / `tests/fixtures/good_upstream.md`), a code touch map
against the real current tree, and a cutline.

### CP-1: `rename-cli-and-positioning` (v1, first)

Rename the binary from `specgraph` to `planlint`; rewrite README around the
wedge; add the positioning table and explicit non-goals; add a deprecated
`specgraph` alias that delegates and preserves the exit code.

- **Name Gate (resolved):** `specgate` is TAKEN on PyPI. `planlint` and
  `osgraph` are free on PyPI, GitHub, and Homebrew, and absent from `PATH`.
  Chosen name: **`planlint`** (drops the "graph" language the strategy retires;
  conveys "lint your plans"; fits the wedge). `osgraph` is the recorded fallback.
  Ecosystems checked authoritatively: PyPI
  (`https://pypi.org/pypi/<name>/json` → HTTP 404 = free), GitHub repo search
  (0 matches), Homebrew (`https://formulae.brew.sh/api/formula/<name>.json` →
  HTTP 404 = no formula), and `command -v` on `PATH` (absent). npm/cargo/apt
  were not checked — out of scope for a Python CLI; the claim is narrowed to
  the ecosystems actually verified.
- **AC-RP-1:** `planlint detect|init|new|validate|graph|rules` works as a
  console-script entry point; the legacy `specgraph` command prints a one-line
  deprecation to **stderr** and delegates to `main`, preserving the real exit
  code (a literal exit-0 alias would silently pass old CI and is rejected).
  (`make test`)
- **AC-RP-2:** README leads with the wedge sentence and a positioning table;
  the non-goals section lists all six refusals. (docs gate)
- **AC-RP-3 (non-success):** No new authoring, constitution, or MCP surface
  appears in the CLI verb list or `__init__` exports. A `propose`/`apply`/chat
  verb added to `cli.build_parser` fails `make test`.
- **Backwards-compat boundary:** the waiver comment syntax
  `<!-- specgraph:allow ... -->`, the config file `openspec/specgraph.json`,
  and the `[tool.specgraph]` pyproject section keep the `specgraph` name as
  stable contract identifiers (renaming them is a migration, not a CLI rename).
  The env var accepts both `PLANLINT_LOG_LEVEL` (preferred) and
  `SPECGRAPH_LOG_LEVEL` (legacy).
- **Touch map:** `pyproject.toml` (entry point), `openspec_graph/cli.py`
  (`build_parser`, `main_deprecated`), `openspec_graph/log.py` (logger + env
  var), `openspec_graph/graph.py`, `Makefile`, `.github/workflows/ci.yml`,
  `README.md`, `docs/`. New: `tests/test_cli_surface.py` (verb allow-list +
  deprecation guard).
- **Cutline:** if the chosen name collides everywhere, ship the rename as
  `planlint` only after a free name is confirmed — do not ship a colliding
  name.

### CP-2: `add-dialect-cards` (v1) — implemented

> Status: implemented. See the approved spec at
> `openspec/changes/add-dialect-cards/specs/dialect-cards/spec.md`
> (`AC-DC-1..7`) — that spec is authoritative; this section is kept as the
> original sketch. One deviation from the sketch below, decided during
> implementation: the card excludes `StackProfile`'s `root` field (and
> reduces `openspec_root` to a portable `has_openspec_root` boolean)
> rather than including every detected field verbatim — both are absolute
> paths that differ across every checkout/machine/CI run, and would make
> `--diff` report constant false "drift" on nothing but where the repo
> happens to be cloned.

`detect` becomes a product. Emit a machine-readable **dialect card** (stages,
threshold locator, INV source, heading depths, languages) as stable JSON; CI
diffs the card so house-style drift becomes a finding.

- **AC-DC-1:** `planlint detect --format json` emits a stable dialect card with
  a schema version; re-running on an unchanged repo is byte-identical.
  (`make test`, reuses the path-normalization pattern from `test_decomposition`)
- **AC-DC-2:** `planlint detect --diff <prev.json>` exits non-zero and lists
  changed fields when the repo's detected conventions drift.
- **AC-DC-3 (non-success):** `detect` writes nothing to the target repo. A test
  that asserts the target tree's mtime is unchanged across `detect` passes; any
  write fails `make test`. (The read-only guarantee, printed in bold in the
  README.)
- **Touch map:** `openspec_graph/detect.py` (`StackProfile.to_card()`,
  `profile()` is already pure), `openspec_graph/cli.py` (`cmd_detect`), new
  `openspec_graph/dialect_card.py` (schema). Reuses `tests/support.py`.
- **Cutline:** if a clean card schema can't be byte-stable across Python
  3.10–3.13 (dict ordering / set iteration), freeze field order explicitly
  before shipping — do not ship a card that "usually" diffs clean.

### CP-3: `parse-repo-machinery-structurally` (v1) — implemented

> The design below is superseded by the approved spec at
> `openspec/changes/parse-repo-machinery-structurally/specs/machinery-parsing/spec.md`
> (`AC-MP-1..7`, not `AC-PM-*`) — that spec is authoritative; this section is
> kept as a historical sketch, corrected where it was factually wrong.
> Status: implemented — G003/`MAKE_REF` precision, the `machinery.py` core
> parser, and its wiring into `detect.py` all shipped. A follow-up gap in
> the wiring itself (a `define`/`endef` block misparsed as a target, in
> both the structural parser and the legacy-regex fallback it widens with)
> was found and fixed separately; see
> `openspec/changes/fix-makefile-define-block-misparse/`.

Stop regex-scanning prose for thresholds and make targets where the repo
already has the truth as structure. Parse `fail_under`, `[tool.coverage.*]`,
and Makefile targets as structured data. This is the **G003/G004** lesson
generalized (not G002/G001, as this section originally and incorrectly
said — G001/G002 are about criteria completeness, not prose/Makefile
scanning): competitors who only scan markdown will false-positive forever;
we already learned that.

- **AC-MP-5** (was sketched as AC-PM-1): `hard_coded_threshold` (G003) no
  longer flags a threshold when it is the single, unambiguous
  threshold-shaped number on its line and it matches the value read from the
  detected `fail_under` locator — never merely "the value appears somewhere
  on the line," which would wrongly excuse a genuine violation sitting next
  to an unrelated, coincidentally-matching number. **Implemented.**
- **AC-MP-1/2/3** (was sketched as AC-PM-2, and sketched wrong): Makefile
  parsing is a stdlib-only, text-based structural parser
  (`openspec_graph/machinery.py`) that **never shells out to `make`, in any
  form, at any confidence level** — not even as a fallback. The original
  sketch here ("`make -p` parse... if `make -p` is unavailable, fall back to
  regex") is unsafe and was corrected before implementation: GNU Make
  evaluates `$(shell ...)` calls outside a recipe body at parse/read time,
  unconditionally, so no flag combination makes shelling out to real `make`
  safe against an untrusted target repo's Makefile. The structural parser
  resolves multi-target lines and the full GNU Make special-target set;
  variable expansion, `include`s, and conditionals lower confidence and fall
  back to the pre-existing regex detection rather than guessing. **The
  parser is implemented** (`machinery.py`, Milestone 1); wiring it into
  `detect.py` so `G004` actually consumes its output is the remaining step
  (Milestone 2b).
- **AC-MP-6** (was sketched as part of AC-PM-2): the `make`-citation regex
  in spec prose (`MAKE_REF`) now requires backtick-fencing, so `G004` stops
  tripping on the bare English word "make" in prose that is not a stage
  citation. **Implemented.**
- **AC-MP-4 (non-success)**, was AC-PM-3: a threshold or make-target citation
  that is genuinely wrong still fails (G003/G004) at any parser confidence —
  structural parsing does not weaken either rule, it only stops false
  positives.
- **Touch map:** `openspec_graph/parse_semantics.py` (`hard_coded`,
  `MAKE_REF`, `threshold_values`), `openspec_graph/detect.py`
  (`_make_target_facts`, additive `StackProfile` confidence fields),
  `openspec_graph/rules_generic.py` (G003/G004). New:
  `openspec_graph/machinery.py` (structural, stdlib-only, no-subprocess
  Makefile reader — constrained by the AC-DG-4 guard).
- **Cutline:** when structural parsing can't confidently resolve a target
  (an `include`, a conditional, variable expansion), fall back to the
  existing regex `MAKE_REF`-adjacent detection and surface an INFO that
  parsing was low-confidence — never fail closed, and never shell out to
  `make` to try to do better.

### CP-4: `add-waiver-ledger-and-inv-lints` (v1) — implemented

> Status: implemented. See the approved spec at
> `openspec/changes/add-waiver-ledger-and-inv-lints/specs/waiver-ledger/spec.md`
> (`AC-WL-1..13`, not `AC-WL-1..3` — the sketch below under-counted; the
> orphan-invariant check needed its own whole-tree evaluation pathway,
> `rules.evaluate_tree()`, since no per-spec `Rule.check` can express "cited
> by *some* spec in the tree") — that spec is authoritative; this section is
> kept as the original sketch.

Two linked additions. (a) **Waiver ledger**: a machine-readable record of every
`<!-- specgraph:allow G003 reason -->` waiver across the tree — rule, file,
owner, reason. (b) **INV bidirectional**: not only "cited INV exists" (U/G
rule already does this) but "declared INV-n is cited by at least one living
spec, or explicitly waived." Orphan invariants are the other lie.

- **AC-WL-1:** `planlint waivers --format json` emits a ledger of every waived
  rule with file, line, reason, and the owning change package. Stable ordering.
- **AC-WL-2:** New rule `G006` (WARN): a declared invariant cited by no living
  spec and not waived is reported as an orphan invariant.
- **AC-WL-3 (non-success):** A waiver with no `reason` text fails (currently
  waivers are silently downgraded to INFO). `<!-- specgraph:allow G003 -->` with
  no reason fails `make test` — a waiver is a claim that must justify itself.
- **Touch map:** `openspec_graph/parse_semantics.py` (`suppressions` already
  parses the waiver comment — extend to capture reason + position),
  `openspec_graph/rules_generic.py` (new G006 + waiver-reason enforcement),
  `openspec_graph/rules.py` (registry), `openspec_graph/cli.py` (new `waivers`
  verb). New: `openspec_graph/ledger.py`.
- **Cutline:** if owner attribution requires git blame and that is slow on huge
  monorepos, ship reason+file+line first and defer owner to a follow-up — the
  ledger is useful without blame.

### CP-GV: `add-mermaid-graph-export` (v1) — implemented

> Status: implemented. See the approved spec at
> `openspec/changes/add-mermaid-graph-export/specs/mermaid-graph-export/spec.md`
> (`AC-GV-1..9`). Not part of the original CP-1..8 numbering above — added
> from a later planning round covering four capabilities together
> (architecture drift detection, witness mode, policy packs, visualization).
> `add-architecture-drift-lint` (CP-AD, below) has since also shipped;
> `add-witness-mode` (CP-7 above) and `add-rule-pack-plugins`/
> `add-security-policy-pack` remain designed but not yet implemented.

`graph --format json` computed the full dependency graph with no way to see
it. `graph --format mermaid` renders the same graph as a Mermaid flowchart —
text GitHub/GitLab render natively, so a PR diff on `openspec/` can carry an
actual picture. `--format dot` (image rendering, needing an external engine)
stays rejected; this doesn't reopen that non-goal, only adds to it.

- **AC-GV-1..4:** `--format mermaid` emits a valid flowchart with sanitized
  node ids and distinct styling for orphan/missing nodes and broken edges;
  `--format dot` stays rejected, byte-identical message and exit code.
- **AC-GV-5..8:** `graph --change <name>` scopes which specs are rendered —
  but never what feeds the whole-tree orphan-invariant check, which always
  runs unscoped regardless of what's rendered (the same false-positive-orphan
  trap `cmd_validate --change` already guards against, `DEC-WL-003`,
  rediscovered and fixed here as `DEC-GV-001`).
- **AC-GV-9:** companion `tools/render_mermaid.py` renders a previously-saved
  `graph --format json` artifact without re-running `planlint`.
- **Touch map:** new `openspec_graph/mermaid.py`, `openspec_graph/cli.py`
  (`graph --change`/`--format mermaid`), `openspec_graph/graph.py`
  (`build_graph()`'s new scoping param), `openspec_graph/detect.py`
  (`filter_by_change()`, shared with `cmd_validate`). New
  `tools/render_mermaid.py`.

### CP-AD: `add-architecture-drift-lint` (v1) — implemented

> Status: implemented. See the approved spec at
> `openspec/changes/add-architecture-drift-lint/specs/architecture-drift-lint/spec.md`
> (`AC-AD-1..16`). Not part of the original CP-1..8 numbering above — from
> the same later planning round as CP-GV. Re-grounded in a fresh Explore +
> Plan pass before implementation: the original motivation
> (`docs/architecture/c4.md` stating a stale rule count/range) had already
> been fixed twice on this branch by the time this CP was designed; the
> live recurrence of that same drift class (`rules.py`'s own module
> docstring) is what actually motivated the new rules and this change's own
> doc-drift guard. Scoped to ADR citation-checking only — OpenAPI/
> event-schema and a C4 doc-freshness rule pair are explicit non-goals, not
> partial work.

`planlint` already caught one class of citation drift — a spec citing an
undeclared `INV-n`, or a declared invariant no living spec cites (G005/G006).
Nothing extended that discipline to architecture decision records. New rules
`G008` (cited-must-exist) and `G009` (declared-must-be-cited) mirror
G005/G006 exactly; 20 rules total (was 18).

- **AC-AD-1..9:** ADR ids are discovered from either a directory of
  per-decision files or a single index file, extracted by scanning each
  candidate's own text (never filenames, so a zero-padded filename can't
  mismatch a spec's bare citation) — `G008`/`G009` fire and waive exactly
  like `G005`/`G006`. Their `--change` behavior mirrors G006's own split,
  not a single "skip": `validate --change` skips G009 entirely, while
  `graph --change` does the opposite — keeps it unscoped and *includes*
  its findings (`DEC-AD-004`).
- **AC-AD-10..13:** `graph` gains its first new node type since the
  original five, `adr`, reusing the existing `declares` edge type; an
  orphaned ADR gets graph and Mermaid representation the same way an
  orphaned invariant already does, and `broken_links` still equals
  `validate`'s finding count (`AC-GR-4`) with both new rules present.
- **AC-AD-14..16:** a new `tests/test_rule_registry_docs.py` mechanically
  checks every prose claim about the rule count/family ranges against
  `rules.RULES` itself (`AC-AD-14`); a change to `adr_source`/`adr_ids` is
  detected by `dialect_card.diff_cards()`, proving the fields are threaded
  into `_COMPARABLE_FIELDS` (`AC-AD-15`); and no rule ident is reserved for
  the deferred OpenAPI/event-schema work (`AC-AD-16`).
- **Touch map:** new `ADR_REF`/`adr_refs` (`parse_semantics.py`/
  `parse_model.py`/`parse.py`), `detect.py` (`ADR_SOURCES`/`_adrs()`/
  `StackProfile.adr_source`/`adr_ids`/`adr_source_name`), `dialect_card.py`
  (`_COMPARABLE_FIELDS`), `rules_generic.py`/`rules.py` (`G008`/`G009`,
  `evaluate_tree()`), `cli.py` (`--change` heads-up lines), `graph.py`
  (`adr` node type, rule-aware `_add_tree_finding_edges()`). New
  `tests/test_rule_registry_docs.py`.

### CP-5: `add-delta-lint` (v1, the org-visible feature)

When `Makefile` / `pyproject.toml` / `CONTRACT.md` changes, list every spec
that still points at the old world. This is the feature a staff engineer
actually wants: "you changed the coverage floor; here are the 7 specs that
still cite the old number."

- **AC-DL-1:** `planlint delta --since <ref> --format json` lists specs whose
  cited make targets, threshold, or invariant set changed because machinery
  changed between `<ref>` and HEAD.
- **AC-DL-2:** A spec that cites a make target removed since `<ref>` is
  reported as stale with the removed target named.
- **AC-DL-3 (non-success):** A repo with no machinery changes since `<ref>`
  exits 0 with an empty list — delta lint does not manufacture findings.
- **Touch map:** `openspec_graph/detect.py` (compare two `StackProfile`s),
  `openspec_graph/cli.py` (new `delta` verb), new
  `openspec_graph/delta.py` (git diff of machinery files + cross-reference
  against parsed specs).
- **Cutline:** if the target repo is not a git repo, exit 0 with an INFO that
  delta lint requires a git history — do not guess.

### CP-6: `add-sarif-and-actions` (v4, distribution)

SARIF output so findings appear inline in the GitHub PR the org already has,
plus a one-file composite Action and a pre-commit hook. Time-to-first-red-X
under five minutes.

- **AC-SA-1:** `planlint validate --format sarif` emits SARIF 2.1.0 consumable
  by GitHub code scanning; the same findings as `--json`, no divergence.
- **AC-SA-2:** A composite Action in `.github/actions/planlint/action.yml`
  runs `detect` + `validate` on a foreign checkout with no setup beyond the
  action; documented time-to-first-red-X < 5 min on a clean repo.
- **AC-SA-3 (non-success):** `validate --format sarif` writes nothing outside
  the SARIF stream; it does not create a side-channel report file or post to
  any API. A test asserts the only artifact produced is the SARIF on stdout.
- **Touch map:** new `openspec_graph/sarif.py` (Finding→SARIF mapping; reuses
  `rules.Finding`), `openspec_graph/cli.py` (`--format` on `validate`),
  `.github/actions/planlint/`, `.github/workflows/` (a sample), `pre-commit`.
- **Cutline:** if GitHub's SARIF schema rejects a finding shape, map down to
  the supported subset rather than dropping findings — every ERROR must survive
  the round-trip.

### CP-7: `add-witness-mode` (v2, the line competitors can't cross)

`validate --require-witness` fails unless CI uploaded a witness stub for each
cited gate: target name, exit code, coverage number read from the detected
locator, commit SHA. Specs stop being fan fiction.

- **AC-WM-1:** `planlint witness record --target test --exit 0 --coverage 97
  --sha <sha>` writes a signed (hash-chained) witness stub to
  `.planlint/witnesses/`; `validate --require-witness` fails if any cited
  `_Verified by:` target lacks a matching stub.
- **AC-WM-2:** A witness whose coverage number is below the detected
  `fail_under` floor fails `validate`, even with exit code 0 — the witness
  proves the gate ran *and* that its number was real.
- **AC-WM-3 (non-success):** `validate --require-witness` fails closed if the
  witness store is absent or untrusted; it never silently treats "no witness"
  as "passed." A repo with zero witnesses and `--require-witness` exits
  non-zero.
- **Touch map:** new `openspec_graph/witness.py` (schema, hash-chain, verify),
  `openspec_graph/cli.py` (`witness` verb + `--require-witness` flag on
  `validate`), `openspec_graph/rules_harness.py` (H001 verifies witness when
  flag set). New rules `W001`/`W002` (missing witness, witness below floor).
- **Cutline:** witness mode is opt-in (`--require-witness`); default `validate`
  behavior is unchanged so the tool stays useful without CI integration. This
  is the v2 line — do not let it destabilize v1.

### CP-8: `add-agent-threat-corpus` (v4, the eval + the marketing)

Keep G002 (require a named reject/deny/fail-closed path) as the brand rule.
Add an **anti-clone rule** (fail if a spec's `_Verified by:` set is identical
to a sibling package's and the Makefile targets it cites were never touched —
agents copypaste stages). Publish a 20-spec agent-failure corpus as a public
eval suite, plus a two-repo comparison table as the homepage.

- **AC-AC-1:** New rule `H007` (WARN): a spec whose `_Verified by:` target set
  exactly matches a sibling change package's, and whose cited Makefile targets
  show no git activity, is flagged as a likely clone.
- **AC-AC-2:** `tests/agent_corpus/` ships 20 broken specs drawn from real
  Mango / Mouse-Droid / hex-vision failures; `planlint validate` catches the
  intended failure in each. Catch rate is a CI-exposed number, not a claim.
- **AC-AC-3 (non-success):** A passing spec in the corpus that `planlint`
  *should* reject fails the suite; the corpus is an eval, not a victory lap.
  The suite fails if catch rate drops below the recorded baseline.
- **Touch map:** `openspec_graph/rules_harness.py` (H007 anti-clone),
  `openspec_graph/rules.py` (registry), new `tests/agent_corpus/` (20 specs +
  expected-findings manifest), new `tools/run_agent_corpus.py` (reports catch
  rate), `README.md` (homepage comparison table).
- **Cutline:** if a real-failure spec cannot be reduced to a non-proprietary
  fixture, drop it from the public corpus and keep only the 20 that are
  publishable — the corpus's value is reproducibility, not count.

---

## Code Touch Map (summary, against the current tree)

| Package | Existing files touched | New files |
|---|---|---|
| CP-1 rename | `pyproject.toml`, `cli.py`, `__init__.py`, `README.md`, `docs/` | `tests/test_cli_surface.py` |
| CP-2 dialect cards | `detect.py`, `cli.py` | `dialect_card.py` |
| CP-3 structural machinery | `parse_semantics.py`, `detect.py`, `rules_generic.py` | `machinery.py` |
| CP-4 waiver + INV | `parse_semantics.py`, `rules_generic.py`, `rules.py`, `cli.py` | `ledger.py` |
| CP-GV mermaid export | `cli.py`, `graph.py`, `detect.py` | `mermaid.py`, `tools/render_mermaid.py` |
| CP-5 delta lint | `detect.py`, `cli.py` | `delta.py` |
| CP-6 SARIF + actions | `cli.py`, `.github/workflows/` | `sarif.py`, `.github/actions/planlint/` |
| CP-7 witness mode | `cli.py`, `rules_harness.py` | `witness.py` |
| CP-8 agent corpus | `rules_harness.py`, `rules.py`, `README.md` | `tests/agent_corpus/`, `tools/run_agent_corpus.py` |

All new modules must remain stdlib-only (enforced by the existing AC-DG-4
guard from `decompose-god-files`) and obey the import boundary (AC-DG-6: no
module below the hub layer imports `cli` or `graph`).

---

## Risk / Cutline Table

| Risk | Trigger | Cutline |
|---|---|---|
| Name collision | `specgate` taken on PyPI/GitHub | Use confirmed-free fallback; never ship a colliding name |
| Card non-determinism | dialect card diffs "clean" across runs | Freeze field order before shipping |
| Structural Makefile parse is low-confidence | `include`, conditional, or variable expansion in target position | Fall back to regex detection + INFO; never fail closed, never shell out to `make` to try harder |
| Witness mode destabilizes v1 | `--require-witness` changes default | Opt-in flag only; default `validate` unchanged |
| Mermaid diagram illegible/invalid at scale | unsanitized node ids break syntax; an unscoped whole-tree diagram exceeds real render limits | Synthetic node ids (mandatory, not cosmetic); `--change` scoping so a diagram covers one change, not the whole portfolio |
| SARIF finding loss | GitHub rejects a finding shape | Map to supported subset; never drop ERRORs |
| Corpus non-reproducible | real-failure spec is proprietary | Drop from public set; keep only publishable fixtures |
| Anti-clone false positive | sibling packages legitimately share a stage | H007 is WARN; require *both* identical set AND no git activity |
| Scope creep into authoring | someone wants a `propose`/`apply` verb | Rejected by AC-RP-3 guard; do not add |

---

## First Three PRs to Execute (in order)

1. **CP-1 `rename-cli-and-positioning`** — but only after the Name Gate
   clears. Includes the README wedge, comparison table, non-goals, and the
   `test_cli_surface.py` verb allow-list guard. This is the cheapest change
   that makes the product *read* as the wedge. Doc-only branch or feature
   branch off `main` after PR #4 merges.

2. **CP-3 `parse-repo-machinery-structurally`** — the highest-leverage v1
   change: it removes the G003/G004 false-positive class the competitors will
   always have, and it is the foundation for delta lint (CP-5) and witness
   coverage numbers (CP-7). In progress — see the CP-3 section above for
   current status.

3. **CP-2 `add-dialect-cards`** — turns `detect` into a product and makes the
   read-only guarantee a tested invariant. Together with CP-3, this is the v1
   moat: structural machinery parsing + a diffable, read-only dialect card.

CP-4 through CP-8 follow once the v1 moat is real, in the order:
CP-4 → CP-5 (v1 complete) → CP-7 (v2) → CP-8 + CP-6 (v4, distribution + eval
land together so the public corpus and the SARIF/Action path ship as one
story).

---

## Winning Move (restated)

Remain the thing you point at someone else's clone. The moment this becomes a
place people write specs, you are in a feature race with 60k-star tools and
you lose. Every package above either sharpens "is this clone's plan lying
against its own machinery" or proves the answer with a witness — nothing
else.
