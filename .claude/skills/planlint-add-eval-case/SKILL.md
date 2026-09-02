---
name: planlint-add-eval-case
description: Add, rename, or remove a case in planlint's agent-skill evaluation suite under evals/, and update every location that must stay in sync with it. Use when writing a new eval case, changing a case's tags or graders, or editing evals/README.md.
---

# Adding an evaluation case to planlint

Same reason as the `planlint-add-rule` skill: the real list of places to touch is longer than intuition suggests, and the tests that enforce it are structural, so a half-added case fails in a way that names a schema key rather than the mistake. `evals/README.md` is an index checked in **both** directions — a case with no row and a row with no case each fail — and that is the step people skip.

A second reason specific to this suite: a malformed grader does not fail, it *grades nothing and reports a pass*. A `regex` grader with no `pattern`, or an LLM grader with an empty rubric, is worse than no grader at all, because the case now looks covered. `tests/test_agent_artifacts.py` exists to catch exactly that.

## Steps

1. **Decide the family first, because it decides the tag and the README table.** Activation, repair and routing cases go in the first table; anything asking the agent to make a finding disappear without changing the fact behind it goes in the adversarial table and must carry the `adversarial` tag. A routing case is the inverse: the skill must *not* activate, and its graders assert the CLI was never invoked.
2. **Create `evals/<case-name>/prompt.md`.** Frontmatter needs `name` (identical to the directory name), `tags`, `plugins`, `max_turns`. Every tag must already be in `_TAGS` in `tests/test_agent_artifacts.py` — add one there deliberately rather than inventing it in a case, or the case silently drops out of every tag-filtered run. `plugins` must name the plugin manifest's own `name`, not the skill directory's.
3. **Write at least one grader** under `evals/<case-name>/graders/`. Prefer a deterministic one wherever the forbidden move leaves a trace: a `regex` grader over `commands` or `files_changed` catches the act regardless of what the agent said about it. Reserve `llm` graders for failures that are purely rhetorical — reporting a pass, omitting a verdict — where there is no argv or file-state signal. Most good cases carry both.
4. **Give every grader the fields its type requires.** A `regex` grader needs `pattern` (which must compile), `match` (`true`/`false`), and `target` (`commands` or `files_changed`). A `tool_used` grader needs `tool` and `should_use`. Every grader needs a non-empty rubric body under the frontmatter.
5. **Add the row to `evals/README.md`**, in the table matching the family from step 1. This is the step the bidirectional index check exists for.
6. **Do not state a case count** in any prose. Counts in this repo are guarded numbers or they are drift; the suite deliberately describes itself without one.
7. **Run `pytest tests/test_agent_artifacts.py`** and fix every failure it reports rather than guessing which file is out of sync.
8. **Run `make pre-pr`** before considering the case done.

## Checking the case actually works

Structural tests prove the case is well-formed, not that it discriminates. Where the runner is available, `claude plugin eval` runs a case against the plugin; a case that passes with the plugin disabled is testing the base model, not this skill. Do not commit raw transcripts — `make security` scans every tracked file and CI runs gitleaks over full history, so a pasted log is the likeliest place a credential lands and the hardest place to remove it.
