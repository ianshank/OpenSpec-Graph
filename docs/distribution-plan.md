# planlint distribution plan

> Planning artifact, not a change package. It supersedes an earlier plan
> ("Publish `planlint-spec-governance`") that was written against `875ab72`,
> before `add-agent-skill-distribution` merged. Current as of that merge.
> Contract changes named below get their own OpenSpec change package; nothing
> here authorizes an edit on its own.

The skill, its generated catalog and manifests, the retrieval config, the
evaluation suite and the release workflow all exist. What does not exist is a
**release**: no tag has been pushed, so nothing has been published, so every
install line this repository prints is currently a lie. That is the whole
critical path. Everything else on this page is hygiene that should not delay
it.

---

## 1. Where we are

| Original plan item | Status | Evidence |
|---|---|---|
| Decide the distribution name | Done | `pyproject.toml` `[project] name = "planlint"` |
| Adopter-facing rename off `OpenSpec-Graph` | Done | one historical mention remains, in a merged change package |
| Skill tree, references, CI asset | Done | `skills/planlint-spec-governance/` |
| Rule catalog generated, staleness gated | Done | `tools/render_rule_catalog.py`, `test_rule_catalog_is_fresh` |
| Claude plugin + marketplace manifests | Done, generated | `tools/render_plugin_manifests.py` |
| Trusted-publishing release workflow | Done, never run | `.github/workflows/release.yml` |
| `context7.json` committed | Done | repo root |
| `llms.txt` committed | Done | repo root |
| Evaluation suite | Done, with defects | `evals/`, see §2 |
| Machine-readable findings schema | **Done** | `add-findings-json-envelope`; `validate --json` carries `schema_version` + `tool_version`, paths relative |
| `AGENTS.md`, name disambiguation | **Not started** | §4 slice 1 |
| Tag, publish, index, topics | **Not started** | §3 |
| Wrapper script, `--version --json`, per-agent copies, dataset export | **Cut** | §5 |

## 2. Facts the earlier plan, or the tree, got wrong

Each row was checked against the checkout or the live index, not inferred.

| Claim | Reality |
|---|---|
| `0.1.0` was never tagged (CHANGELOG) | `v0.1.0` exists on `origin` at `cdc94ca`, under the pre-rename distribution name |
| `v0.2.0` is the first tagged release, first published to PyPI (CHANGELOG) | No `v0.2.0` tag exists; the release workflow has never run; nothing is published |
| The distribution name was undecided | Decided and merged; `planlint` is free on PyPI, `plan-lint` is taken by an unrelated project |
| `pip install planlint` works (README, skill preflight, CI template) | It does not, and will not until §3 completes |
| Findings JSON is portable | `validate --json` emits absolute, native-separator paths and no schema version, while the CI template uploads that file as a cross-machine artifact |
| Evaluations are graded on tool calls and file state (both READMEs) | Most cases are adjudicated by a model reading the transcript; only a few carry a deterministic grader |
| One evaluation case proves the skill refuses to record a witness | Its grader forbids the shell outright, so a correct run that invokes the CLI fails it |
| Eval summaries belong under `reports/` | The runner writes a `results/` directory, which the structural test would read as a malformed case |
| `--json` is the way to get either command's structured output (skill body) | For `detect` it selects a legacy shape with machine-specific paths; the portable card is `--format json` |
| Three files in the tree are generated (architecture doc) | Four are enumerated in the same sentence, and one of them has no `--check` mode |
| The skill's own metadata version tracks the package | It does not, and nothing guards it |
| A wrapper script is needed so agents can invoke the CLI | The project already declined a wrapper, for reasons that still hold |
| Copies of the skill are needed under other agents' directories | The marketplace source form in use is the documented one, and the skill carries no repository-relative references |

## 3. Phase 0 — release unblock

Manual, outside the repository, in this order. Nothing in §4 blocks these
except where noted.

1. Confirm the distribution name is still unclaimed on PyPI.
2. Register a **pending trusted publisher** on PyPI: project `planlint`, owner
   `ianshank`, repository `planlint`, workflow `release.yml`, environment
   `pypi`. The environment string must match the release workflow's
   `environment:` value exactly; a mismatch fails only at the final step,
   after the whole gate has already run.
3. Create the GitHub environment `pypi`. A required reviewer here means the
   publish job waits for approval rather than failing.
4. Land slice 2 (§4). The findings-JSON change is breaking, and shipping it
   after the first publish makes it a break for real adopters instead of a
   free correction.
5. Tag the merge commit whose package version matches the tag, and push the
   tag. The build job compares the two and fails on a mismatch.
6. Watch the three jobs. `gate` is the first time the full pre-PR ladder runs
   in continuous integration; `build` is the only thing anywhere that
   exercises the installed console script; `publish` needs the OIDC identity
   from step 2.
7. Install the published distribution into a fresh virtual environment, run
   the version command, and re-run by hand every install line this repository
   prints.
8. Create the GitHub release from the changelog section. Add the repository
   topic for agent skills.
9. Submit the repository to Context7. The committed configuration means the
   indexed scope does not depend on choices made in a web form.

**Exit criterion:** every install line in the README, the skill's preflight
step, and both copies of the CI template resolves.

## 4. Phase 1 — in-repo slices

### Slice 1 — hygiene, guards, evaluation fixes

No published contract changes. Files and the test that pins each:

| Work | Files | Pinned by |
|---|---|---|
| Agent entry point | `AGENTS.md`, `.dockerignore` | link-resolution test alongside the existing one for `llms.txt` |
| Name disambiguation | `README.md`, `llms.txt`, `context7.json` | `tests/test_adopter_urls.py` |
| Install-line guard | `tests/test_adopter_urls.py` (new) | itself |
| Changelog corrections | `CHANGELOG.md` | `tests/test_adopter_urls.py` |
| Architecture doc corrections | `docs/architecture/c4.md` | prose review |
| Stale milestone sentence | the merged change package's `tasks.md` | `make validate` |
| Skill metadata version + policy | `SKILL.md`, `docs/hooks.md` | new test in `tests/test_agent_skill_docs.py` |
| Evaluation defects and gaps | `evals/**` | `tests/test_agent_artifacts.py` |
| Structural test tightening | `tests/test_agent_artifacts.py` | itself |
| Unpinned exit-code quotes | `tests/test_skill_contract.py` | itself |
| Build backend in the dev extra | `pyproject.toml` | none needed |

**Merge gate:** `make pre-pr`, plus both generator `--check` modes, plus a
self-validation run at the warning level so the graph-diff job cannot regress.

### Slice 2 — findings JSON envelope — **shipped**

> Shipped as `add-findings-json-envelope`, before the first tag, exactly as
> the sequencing below required. `DEC-FE-001` records the supersession and
> narrows it honestly: the artifact-upload evidence defeats `DEC-PS-002`'s
> first argument only, and `Finding.as_dict()`'s default stays absolute for
> backwards compatibility. `detect --json` was deprecated in the same change,
> since removing a flag after publication is a break.

Its own change package, because it supersedes a recorded decision. The
decision held that absolute paths were acceptable because none of the affected
fields is ever compared across two checkouts. The CI template refutes that: it
uploads the findings file as a build artifact, produced on a runner and read
elsewhere.

Shape of the work: give each finding a repository-relative POSIX path, using
the helper already applied at every other call site; wrap the payload in a
schema version and the tool version; keep the top-level target absolute, since
it is now the base those relative paths resolve against; keep the existing key
spelling, because renaming it is a second break that buys nothing. Re-pin the
golden output hash and normalize the version out of that fixture so future
releases stop re-pinning it.

### Slice 3 — evaluation fixtures (optional, later)

Per-case scaffolding would unlock file-state graders for the destructive
cases and a discovery case where both dialects are present. Not a gate: the
existing stance on running the suite in continuous integration stands.

## 5. Deferred, with the trigger that reopens each

| Deferred | Reopen when |
|---|---|
| A wrapper script inside the skill | A named consumer cannot shell out to the CLI directly |
| Version output as JSON, with a ruleset fingerprint | A consumer needs the fingerprint and the version in one call; today the rules verb and the version flag cover it between them |
| Exporting the evaluation suite as a dataset | Someone wants to run these cases outside the runner they were written for; the export is mechanical from what is already committed |
| Copies of the skill under other agents' directories | An agent's installer cannot read a skill directory from a git source |
| Declaring allowed tools in the skill frontmatter | A recorded evaluation failure traces to a permission prompt, and only after confirming what the declaration pre-approves |
| Running the evaluation suite in continuous integration | A headless, deterministic runner exists |
| A freshness check target in the pre-PR ladder | A stale generated artifact reaches CI, contradicting the reasoning that keeps writers out of the gate table |

## 6. Non-goals

Unchanged from the project's standing position: no spec authoring, no MCP
server, no rename of the import package or the waiver prefix, no container as
the primary delivery path, and no skill capability that would let an agent
write a waiver, record a witness, or edit a threshold. Added here: no second
copy of the skill inside this repository, and no claim in the README about an
agent load path this project has not tested.

## 7. Verification ledger

```
make pre-pr
python tools/render_plugin_manifests.py --check
python tools/render_rule_catalog.py --check
planlint --target . validate --fail-on WARN
```
