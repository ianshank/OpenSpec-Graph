# Eval corpus strategy — peer review and rewritten plan

> Planning artifact, in the style of `docs/differentiation-roadmap.md`. Not
> implementation. Every factual claim below was checked against this tree at
> `7cb2bd6` or against a read-only clone of `ianshank/Agents`, and each carries
> a confidence tag: **[Certain]** reproduced or read directly, **[Likely]** a
> strong inference from evidence, **[Guessing]** a gap filled by judgement.

## What this reviews

Two rounds of multi-model research (Kimi K3, Gemini 3.7 Flash Thinking,
Claude Opus 5 Thinking) on adapting the `eval-corpus-forge` Agent Skill from
`ianshank/Agents` into planlint's CI. Round one designed a generic
"forge plane / gate plane" architecture; round two asked whether the forge is
useful to planlint at all. Both rounds admitted they could not fetch the
skill's `SKILL.md`.

Each decision below is written as **Thesis** (the research's position),
**Counter-argument** (the strongest case against it), and **Rebuttal** (a
different position that survives both, not a defence of the thesis). The
rewritten plan follows the decisions.

## Ground truth the research did not have

| Fact | Confidence | Where checked |
|---|---|---|
| `eval-corpus-forge` makes no model call and generates nothing. It is a stdlib normaliser: ingest JSON/JSONL/CSV/transcripts → deterministic `scn_<sha256[:16]>` ids → ground truth split out → four view files → validate → atomic swap. Its own text says "never fabricate" and "no silent inference in v1". | [Certain] | `skills/eval-corpus-forge/SKILL.md` (144 lines), `scripts/forge/*.py` (1,334 lines, no network or API import) |
| Both research rounds assumed the forge is an LLM generator and architected around cost, nondeterminism, cassette replay, and ratifying LLM-authored ground truth. None of that problem exists. | [Certain] | The two research documents versus the file above |
| `claude plugin eval` is installed here (CLI 2.1.259) but the account is not enrolled: the runner prints `plugin eval is currently in early access` and does nothing. The suite under `evals/` has never been executed by its intended runner. | [Certain] | Ran `claude plugin eval --case which-dialect --runs 1 --max-cost-usd 0.40` in this session |
| The grader targets the suite uses, `commands` and `files_changed`, exist as strings in the CLI binary but appear in no published documentation. | [Likely] | `grep` of the CLI bundle; a documentation search found no page for the command |
| `Requirement.is_normative` is a bare substring test on `SHALL`/`MUST` with no word boundary. "shallow clone" and "Marshalling" count as normative and silence U004. | [Certain] | `openspec_graph/parse_model.py:59-61`, reproduced |
| On an adversarial 86-sentence hand-labelled set, `Criterion.is_negative` scored precision 0.38, recall 0.42. Worst regexes: `\bblock(s\|ed\|ing)?\b` (6 false, 1 true), `\bzero\b` (5 false, 1 true, and redundant with `non-?zero`), `\bfail\w*` (swallows failover, failsafe, failure-rate). Patterns with zero false positives: the structural ones (`opens no`, `no X is created`, `neither`, `cannot`, `never`, `non-success`). | [Certain] on the numbers, [Likely] that field precision is higher because the set was built knowing the regex list | Scratch probe against `openspec_graph.parse_semantics.NEGATIVE_PATTERNS` |
| A false positive silences G002 for the whole spec ("the block renders below the header" satisfies "at least one non-success criterion"). The false-positive side is the dangerous one. | [Certain] | `rules_generic.py:_needs_negative` |
| Twenty synthetic target repos built in one sitting found 5 wrong detections and 2 crashes: a UTF-8 BOM turns the first Makefile target into `﻿all` and produces a **false G004** on a valid repo; `_FAIL_UNDER` matches `fail_under` under any TOML table and mislabels the locator; a float floor `85.5` is reported as `85`; a directory named `Makefile` or `pyproject.toml` raises `IsADirectoryError` with exit 1. | [Certain] | All four reproduced by hand in this session; `detect.py:72`, `detect.py:239`, `detect.py:297` |
| The hostile-Makefile invariant holds. A Makefile with `$(shell rm -rf <canary>)`, a bare `$(shell touch …)`, `$(eval $(shell …))`, `.SHELLFLAGS` and `.ONESHELL` was parsed with no side effect. The control run under `make -n` deleted the canary, so the test is meaningful. A 10 MB Makefile with 252,307 targets parses in about a second. | [Certain] | Probe with canary directory and control |
| The Agents repo grades skills with `skills/common/skill_validator.py`, whose `command_exit_zero` assertion runs any shell command and keys on its exit code. Two OpenSpec-authoring skills, `openspec-quality-plan` and `openspec-peer-review`, are `EXEMPT` from skills CI because they had no objective grader. `planlint --target . validate --fail-on ERROR` already exits 0 on that repo. | [Certain] | `skill_validator.py:301-314`, `.github/workflows/skills-ci.yml:483-487`, live run |
| `flow-corpus`'s `Oracle` protocol is two members and a planlint oracle would satisfy it, but nothing gates until κ ≥ 0.8 over ≥ 100 human-audited pairs (`kappa_gate.py:77`, `config.py:78,82`). | [Certain] | Read directly |
| The roadmap already contains the corpus idea in a different shape: CP-8 `add-agent-threat-corpus` (20 broken specs, CI-exposed catch rate). `docs/next-steps.md` item 16 records that the eval suite has no CI job and item 7 that `detect --diff` has no CI wiring. | [Certain] | `docs/differentiation-roadmap.md`, `docs/next-steps.md` |

## Decisions

### D1 — Where the forge belongs

**Thesis.** All three models: the forge runs on an outer plane, nightly or on
dispatch, never inside `make pre-pr`, because an LLM generator in a merge gate
produces irreproducible red builds.

**Counter-argument.** The forge is deterministic, stdlib-only, and needs no
key. It could sit inside `make pre-pr` today at zero cost. The two-plane
architecture solves a nondeterminism that is not there.

**Rebuttal.** Both positions answer the wrong question. The forge's job is to
package existing prompts, traces, and expected outcomes. planlint has nothing
for it to package: the eval runner is not enabled, `evals/results/` is
gitignored and by policy never committed, and no export writer exists. A
packager with no input has no plane to live on. The correct dependency
direction is the one Claude Opus 5 Thinking noticed and ranked fourth:
planlint is a grader **for** the Agents repo (D6), and the forge is a
downstream consumer of a scrubbed eval export that does not exist yet (D5).
**Decision: no forge integration in planlint now.** Not in `pre-pr`, not
nightly, not as an optional extra.

### D2 — First target: detection, as a corpus of labelled target repos

**Thesis.** Claude Opus 5 Thinking: planlint has been validated against two
real repositories; `detect` is the load-bearing primitive; build a matrix of
labelled synthetic target repos diffed against `detect --format json`.

**Counter-argument.** Kimi K3 and Gemini 3.7 both rank this below Agent Skill
evals. The structural Makefile parser and dialect card already shipped with
their own determinism tests, and every shape the probe found "unsupported"
(tox.ini, Gradle, vitest, followed includes) is a documented non-goal, not a
bug. A corpus that mostly confirms design limits is busywork.

**Rebuttal.** The probe is the evidence. Twenty shapes, one sitting, and the
result was five wrong detections and two crashes, one of which is a false
G004 on a valid repo, the exact false-fire class the README already documents
finding by hand. That was found with `printf` and `expected.json`, no LLM, no
corpus infrastructure. The counter-argument is right that a separate corpus
runner would be over-built. So the shape is not "a corpus": it is
`tests/corpus/targets/<shape>/{repo/, expected.json}` consumed by one
parametrised test that compares `to_card()` output to the expectation through
`dialect_card.diff_cards()`, the comparison function that already exists.
The hostile-Makefile specimen goes in with its canary and becomes a permanent
assertion, turning the no-shell-out invariant from an import guard into a
behavioural one. `detect --diff` gets no new CI job; the parametrised test
**is** the drift gate, and `next-steps.md` item 7 can be closed by reference.

### D3 — Mutation testing and property-based testing

**Thesis.** Claude Opus 5 Thinking: mutmut and Hypothesis over the negation
matcher and the parsers outrank corpus generation on cost per bug found.

**Counter-argument.** Mutation testing on a regex-heavy parser produces
mostly equivalent mutants and noise, the suite's wall time multiplies by the
mutant count, and a mutation score is a number that would need a floor
somewhere, which planlint's own G003 discipline forbids in Make or YAML.

**Rebuttal.** _(Filled from the measurement run; see the appendix for the
raw numbers.)_ PLACEHOLDER_D3

### D4 — The G002/U004 phrasing corpus

**Thesis.** All three models: this is the best-justified narrow use of a
phrasing corpus, because "does this sentence assert a non-success outcome" is
a cheap binary label and the README names the failure mode exactly.

**Counter-argument.** A corpus measures; it does not fix. Precision 0.38 on
the adversarial set says the matcher is wrong in kind, not merely
under-sampled: bare-word lexical triggers (`block`, `zero`, `fail`, `without`)
fire on ordinary software prose, and no amount of labelled data changes that.
The labeller also could not decide 11 of 97 sentences, which caps how
consistent a second labeller would be with the first. And the forge cannot
author the sentences anyway (D1).

**Rebuttal.** Do both in one change, the way this repo already handles
linter faults: the fix and the regression evidence land together, named after
what exposed them. The corpus is a committed pytest fixture of about a
hundred hand-ratified sentences, half negative and half success-with-trap-
words, plus the ambiguous ones kept in a separate file that asserts nothing.
The fix is design work for `spec-drafter` and `spec-adversary`, not a regex
edit: the probe shows the structural patterns have zero false positives and
the lexical ones carry all the damage, which suggests a two-tier matcher
(structural patterns decide; lexical ones only when anchored to an outcome
clause). U004 is simpler and unambiguous: `\b(SHALL|MUST)\b`. Per-rule
precision and recall are **reported** in `docs/aqa.md` as measured on the
committed set, with the adversarial caveat stated, and are not gated. A
precision floor in Make or YAML would violate G003; a floor in
`pyproject.toml` is possible later but is not earned until the number has
been stable for a while.

### D5 — The Agent Skill evaluation suite

**Thesis.** Kimi K3 and Gemini 3.7: forge adversarial prompts (waiver evasion,
witness faking, floor tampering) around the existing trace oracles.

**Counter-argument.** Claude Opus 5 Thinking: trap design is the whole value;
generated variants dilute it. Anthropic's own guidance is 20 to 50 tasks drawn
from real failures, and the suite already has 24 hand-authored cases graded on
`commands` and `files_changed`.

**Rebuttal.** Both sides argue about authorship while the suite has never
run. The runner is early-access and not enabled on this account, and the
grader targets the suite depends on are undocumented. Until one real run
exists, adding cases of either provenance adds unverified YAML. The action is
to get the suite executed once (early-access enrolment, or a manual run by a
maintainer with access), commit the scrubbed summary the README already asks
for, and confirm the grader vocabulary is accepted. `next-steps.md` item 16
stays accurate. Only after that does a scrubbed export exist for the forge to
package, and only then is D1 worth revisiting.

### D6 — planlint as the grader inside the Agents repo

**Thesis.** Claude Opus 5 Thinking: invert the dependency; planlint's exit
contract is a ready-made verifier for any skill that writes an OpenSpec
package.

**Counter-argument.** It is a different repository, `command_exit_zero`
collapses exit 2 (no spec tree) into "fail", and the `flow-corpus` κ gate
needs 100 human-audited pairs before any oracle may block a ship decision.

**Rebuttal.** The κ objection applies only to the ship/hold/escalate gate in
`behavioral-regression`, which is the wrong integration point. The right one
is skill CI: `openspec-quality-plan` and `openspec-peer-review` are exempt
from CI because they were ungradeable, and a `command_exit_zero` assertion
over their generated package is exactly the objective grader they lack.
That is four files in the Agents repo and none in planlint. The exit-2
conflation is handled by pairing the assertion with a `detect` precondition
assertion. The `flow-corpus` oracle is explicitly rejected: κ ≥ 0.8 over 100
human pairs costs more than the value, and `TaskInstance` has no path field.

### D7 — Gate math, thresholds, and workflows

**Thesis.** Bootstrap confidence intervals, a hard-fail safety subset, three
workflows including a baseline-on-main job, cassette refresh.

**Counter-argument.** Every artefact this plan produces is deterministic
pytest. There is no sampling variance to bound and no baseline to refresh.

**Rebuttal.** The counter-argument stands, and the one place it needs
sharpening is thresholds. No new number enters the Makefile or any workflow.
The only numbers this plan introduces are the labels in `expected.json` and
the sentence corpus, which are data, not gates. If a mutation-score or
precision floor is ever adopted it goes in `pyproject.toml` beside
`branch_fail_under` and is read by a `tools/check_*.py` script, the pattern
`tools/check_no_hardcoded_thresholds.py` already enforces. No new workflow.

### D8 — Holdout

**Thesis.** Keep Mango and Mouse-Droid as a holdout the forge never sees.

**Counter-argument.** Those two repos are where the four documented
false-fires were found and each became a named regression test. They are the
training set. Holding them out now is theatre.

**Rebuttal.** The nearest thing to an untouched real repo is `ianshank/Agents`
itself: six upstream-dialect change packages, a coverage floor, ADRs, and
planlint has never been tuned on it. It already validates clean at ERROR with
four G009 warnings. It is not a CI holdout, because cloning it needs network
and the gate is offline by design, but it is the right manual pre-release
target, and D6 makes it a repo that runs planlint on every skill change
anyway. If a genuinely foreign repo is wanted, the roadmap's `hex-vision`
mention is the candidate, and it should be scanned once before any rule is
changed for it.

## Rewritten plan

Ordered by cost per defect found, front-loading deterministic wins. Each item
is a change package for `spec-drafter` → `spec-adversary` before code, per
`AGENTS.md`.

| # | Change package | Scope | Gate | Cutline |
|---|---|---|---|---|
| 1 | `fix-detect-corpus-defects` | Fix the four reproduced defects (BOM in `machinery.parse_makefile` and the regex fallback; `_FAIL_UNDER` scoped to its TOML table; float floors preserved; `IsADirectoryError` → exit 2). Add `tests/corpus/targets/` with the twenty shapes and `expected.json` each, one parametrised test through `diff_cards()`, and the hostile-Makefile specimen with its canary. | `make test` | If BOM handling touches the legacy regex path differently, ship the structural fix and file the fallback separately; never leave the false G004 in place |
| 2 | `add-property-tests` | Hypothesis as a dev-only extra. Properties: `parse_makefile` never raises and returns sorted, deduplicated targets for arbitrary text; `strip_define_blocks` is idempotent; upstream requirement count equals heading count for generated specs; `is_negative` is invariant under case and whitespace. Any shrunk failure becomes a named fixture. | `make test` | If a property is flaky under seed, it is a bug in the property, not the code; fix or drop it, never mark it xfail |
| 3 | `add-mutation-target` | mutmut as a dev-only extra behind `make mutation`, **not** in `pre-pr` or `ci`. Scope pinned to `parse_semantics.py`, `machinery.py`, `rules_generic.py`, `rules_upstream.py`. Survivors reviewed by hand; each confirmed gap becomes a test. No score floor until the number has been stable. | `make mutation` (writer, not gate) | If wall time exceeds what a contributor will run locally, restrict to `parse_semantics.py` and `machinery.py` |
| 4 | `fix-g002-u004-matcher-precision` | Two-tier negation matcher (structural decides; lexical only with an outcome anchor); `\b(SHALL\|MUST)\b` for U004. Committed sentence corpus in `tests/fixtures/phrasing/` with ratified labels and a separate ambiguous file. Per-rule precision and recall reported in `docs/aqa.md`, caveated, not gated. | `make test`, `make docs-check` | If the two-tier design cannot reach zero false positives on the committed set, ship U004 alone and keep G002 at WARN-equivalent confidence in the report until it can |
| 5 | Agents repo: `planlint-as-skill-grader` | `evals/evals.json` plus fixtures for `openspec-quality-plan` and `openspec-peer-review` using `command_exit_zero` over `planlint validate --fail-on ERROR`, paired with a `detect` precondition; remove both from `EXEMPT` in `skills-ci.yml`; one added assertion in `openspec-implementation-review`. Nothing changes in planlint. | Agents repo skills CI | cwd is the skill directory; every `--target` is skill-relative |
| 6 | Run `evals/` once | Early-access enrolment or a maintainer run. Commit the scrubbed summary. Confirm `commands` and `files_changed` are accepted. | manual | If the runner rejects the grader vocabulary, fix `tests/test_agent_artifacts.py`'s pinned sets in the same commit |
| 7 | Deferred: `eval-export` → forge | Only after 6 exists: `tools/export_eval_results.py` writes one scrubbed JSONL record per case in the forge's input shape; `run_eval_corpus_forge.py --in <dir>` consumes it unchanged. | `make eval-export` | Do not build until a real results directory exists |

**Explicitly rejected**, with the reason in one line each:

- The forge inside planlint, on any plane: it has nothing to package (D1).
- A nightly `forge.yml`, cassette replay, bootstrap-CI gate math, and a
  baseline-on-main workflow: they solve nondeterminism that is not present (D7).
- Embedding-cosine dedup and Hugging Face or Langfuse sync: network calls in a
  gate that is offline by design.
- Generated adversarial skill-eval cases: unverified YAML on top of a suite
  that has never run (D5).
- A `PlanlintOracle` in `flow-corpus`: κ ≥ 0.8 over 100 human pairs costs more
  than it returns (D6).
- Mango and Mouse-Droid as a holdout: contaminated (D8).
- Any precision, mutation, or pass-rate floor in the Makefile or workflow YAML:
  G003 applies to this repo too (D7).

## Relation to the existing roadmap

- CP-8 `add-agent-threat-corpus` remains the public, spec-shaped corpus with
  a catch rate. Items 1 and 4 above are its deterministic prerequisites: a
  catch-rate claim is only worth publishing once detection and the G002
  matcher are known to be right on labelled input.
- `next-steps.md` item 7 (`detect --diff` CI wiring) is closed by item 1's
  parametrised test rather than by a new job.
- `next-steps.md` item 16 (eval suite has no CI job) stays open and accurate
  until item 6 lands.
- `next-steps.md` item 8 (autonomous spec generation is out of scope) is
  untouched: nothing here authors a spec.

## Appendix — evidence

All probes ran in one session against `7cb2bd6`, in scratch directories,
with no repo file modified. The numbers are reproducible from the specimens
described; none is a claim from memory.

### A. Detection probe (20 target shapes)

| Shape | Verdict | Note |
|---|---|---|
| `setup.cfg` `fail_under`; `.coveragerc` `fail_under` | correct | |
| Monorepo, root Makefile + nested package, harness spec, `CONTRACT.md`, `docs/adr/` | correct | root-only scoping as documented |
| CRLF Makefile | correct | |
| UTF-8 BOM Makefile, `all:` first | **wrong** | targets `["build", "﻿all"]`; downstream `validate` emits a false G004 for `` `make all` `` |
| UTF-8 BOM Makefile, `.PHONY:` first | **wrong** | `"﻿.PHONY"` becomes a target |
| Hostile Makefile (`$(shell rm -rf …)`, bare `$(shell touch …)`, `$(eval $(shell …))`, `.SHELLFLAGS`, `.ONESHELL`) | **safe** | canary survived; control run under `make -n` deleted it |
| Recursive `include` chain | unsupported-by-design | terminates in 0.15 s, confidence `low` |
| 10 MB Makefile, 252,307 targets | correct | 0.84 to 1.28 s, about 112 MB RSS |
| `define`/`endef` with fake targets, nested, indented | correct | |
| Upstream, harness, SpecKit, and mixed dialects | correct | |
| Makefile + `package.json` | correct | Makefile wins for stages, by design |
| tox-only, Gradle JaCoCo, vitest thresholds, followed includes | unsupported-by-design | documented non-goals |
| `fail_under = 50` under `[tool.some_other_tool]` | **wrong** | reported as `[tool.coverage.report].fail_under` |
| `fail_under = 85.5` | **wrong** | reported as `85` |
| `Makefile` is a directory; `pyproject.toml` is a directory | **crash** | `IsADirectoryError` traceback, exit 1 |

Tally: 13 correct, 5 unsupported-by-design, 5 wrong, 2 crashes. The
`make_unresolved_count` field stays 0 on the include cases while confidence
is `low`, which makes the text-mode INFO line misleading; not wrong per the
field's definition, but worth a look in item 1.

### B. G002 / U004 phrasing probe

97 criterion sentences (43 negative, 43 success-with-trap-words, 11
ambiguous), 32 requirement texts. Built in about 150 seconds by a model
that had read the regex list, so the false-positive rate is a stress test,
not a field base rate; the recall figure is more representative.

| Matcher | Precision | Recall | TP / FP / FN / TN |
|---|---|---|---|
| `Criterion.is_negative` (86 unambiguous) | 0.38 | 0.42 | 18 / 29 / 25 / 14 |
| `Requirement.is_normative` (32) | 0.47 | 0.39 | 7 / 8 / 11 / 6 |

False-negative families for G002: status codes as the outcome ("returns
exit 2 rather than exit 0", "yields a 401"); stop/abort verbs (aborted,
halts, declines, skipped, dropped, ignored); "error" as a noun; "is a
no-op"; "leaves the tree untouched". False positives for U004 are all
substring hits: "shallow clone", "Marshalling", "mustard", "must-have",
`MUST_ROTATE_KEYS`, and the question "Shall we keep the legacy endpoint?".

### C. Mutation testing and Hypothesis

PLACEHOLDER_APPENDIX_C

### D. Agents repo integration points

- Grader engine: `skills/common/skill_validator.py`; assertion registry at
  lines 317-325; `command_exit_zero` at 301-314 runs `cmd` verbatim through
  the shell with cwd set to the skill directory, 120 s default timeout.
- Existing JSON-keyed assertions using the same idiom: `eval-corpus-forge`,
  `architecture-drift-guard`, `openspec-implementation-review`.
- Exempt skills: `.github/workflows/skills-ci.yml:483-487`; reason recorded
  in `skills/README.md:54-59`.
- Live run: `planlint --target <agents> detect` exit 0 (upstream dialect,
  6 change packages, floor 96); `validate --fail-on ERROR` exit 0 with four
  G009 warnings on uncited ADRs.
- `flow-corpus` oracle protocol: `flow_corpus/oracles/base.py:17-23`; κ gate
  `oracles/kappa_gate.py:45-93`; power floor `validation/power.py:11-13`;
  defaults `config.py:78,82`.
- Forge input keys the export would need to emit: `prompt`, `scenario_id`,
  `response`, `trace.tool_names`, `trace.tool_invocation_order`, `rubric` or
  `expected_output_fields`, `completion_status`, `taxonomy_tags`
  (`scripts/forge/ingest.py:26-36,245`, `normalize.py:14`,
  `ground_truth.py:12-46`, `views.py:16-19`).

### E. External sources consulted

- Feng et al., *Beyond Model Collapse: Scaling Up with Synthesized Data
  Requires Verification* (arXiv 2406.07515): verifier-filtered synthetic data
  recovers generator-level performance even with an imperfect verifier, and
  a stronger model is not automatically a better verifier. Supports D6's
  direction (a deterministic verifier over generated packages) and argues
  against trusting a generator's own labels.
- Maaz, DeVoe, Hatfield-Dodds, Carlini, *Agentic Property-Based Testing*
  (arXiv 2510.09907): 100 packages, 56% of reports valid, about $10 per
  valid bug; the most productive properties were invariants, round-trips,
  idempotence, and "does not crash" for parsers. Supports D3's property list.
- Kapoor et al., *AI Agents That Matter* (arXiv 2407.01502): agent
  benchmarks are small, overfit without appropriate holdouts, and rarely
  report cost or error bars. Supports D8 and the rejection of an
  uncalibrated gate in D7.
- Anthropic, *Demystifying evals for AI agents* (via secondary summaries;
  the primary page was not reachable from this session): start with 20 to
  50 tasks drawn from real failures; grade on environment state, not the
  final message. Supports D5.
