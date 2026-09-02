"""Deterministic validation of the agent-facing artifacts this repo publishes.

`skills/`, `.claude-plugin/`, `evals/`, `context7.json` and `llms.txt` are
consumed by machines outside this repository: a plugin installer, a retrieval
index, an evaluation runner. None of them is exercised by the CLI, so nothing
else here would notice a malformed manifest, an eval case with no grader, or a
retrieval config scoping a folder that was renamed away.

That is the same argument `tests/test_agent_skill_docs.py` and
`tests/test_rule_registry_docs.py` already make for prose: an artifact only an
external consumer reads needs an internal check, or its first failure happens
in someone else's tool. These are structural checks (shape, required keys,
referential integrity), deliberately not judgements about content.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = REPO_ROOT / "evals"
SKILL_DIR = REPO_ROOT / "skills" / "planlint-spec-governance"
CONTEXT7 = REPO_ROOT / "context7.json"
LLMS_TXT = REPO_ROOT / "llms.txt"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

EVAL_CASES = sorted(p for p in EVALS_DIR.iterdir() if p.is_dir() and p.name != "reports")

# Grader kinds the plugin-eval format defines. A grader naming anything else is
# a typo that would silently never run.
_GRADER_TYPES = frozenset(
    {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
)


def _ids(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def _frontmatter_block(text: str, path: Path) -> str:
    assert text.startswith("---\n"), f"{path}: must open with a '---' frontmatter line"
    return text[4:text.index("\n---\n", 4)]


def _frontmatter(text: str, path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in _frontmatter_block(text, path).splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


# --- evals ------------------------------------------------------------------


def test_eval_suite_is_not_empty() -> None:
    """A silently-empty glob would make every case-level test vacuous."""
    assert len(EVAL_CASES) >= 20, (
        f"expected at least twenty eval cases, found {len(EVAL_CASES)}"
    )


@pytest.mark.parametrize("case", EVAL_CASES, ids=_ids(EVAL_CASES))
def test_eval_case_has_a_prompt_with_required_frontmatter(case: Path) -> None:
    prompt = case / "prompt.md"
    assert prompt.exists(), f"{case.name}: no prompt.md"
    text = prompt.read_text(encoding="utf-8")
    fields = _frontmatter(text, prompt)
    for key in ("name", "tags", "plugins", "max_turns"):
        assert fields.get(key), f"{case.name}: prompt frontmatter missing {key!r}"
    assert fields["name"] == case.name, (
        f"{case.name}: frontmatter name {fields['name']!r} must match the directory"
    )
    body = text.split("\n---\n", 1)[1].strip()
    assert body, f"{case.name}: prompt has frontmatter but no actual prompt text"


@pytest.mark.parametrize("case", EVAL_CASES, ids=_ids(EVAL_CASES))
def test_eval_case_declares_the_plugin_under_test(case: Path) -> None:
    """A case that forgets the plugin tests the base agent, not this skill."""
    fields = _frontmatter((case / "prompt.md").read_text(encoding="utf-8"), case / "prompt.md")
    assert SKILL_DIR.name in fields["plugins"], (
        f"{case.name}: plugins {fields['plugins']!r} does not name {SKILL_DIR.name}"
    )


@pytest.mark.parametrize("case", EVAL_CASES, ids=_ids(EVAL_CASES))
def test_eval_case_has_at_least_one_typed_grader(case: Path) -> None:
    """An ungraded case always passes, which is worse than not having it."""
    graders = sorted((case / "graders").glob("*.md"))
    assert graders, f"{case.name}: no graders; the case could never fail"
    for grader in graders:
        fields = _frontmatter(grader.read_text(encoding="utf-8"), grader)
        kind = fields.get("type")
        assert kind in _GRADER_TYPES, (
            f"{case.name}/{grader.name}: grader type {kind!r} is not one of "
            f"{sorted(_GRADER_TYPES)}"
        )


def test_adversarial_cases_in_the_readme_table_all_exist() -> None:
    """The README's table is the suite's index; a stale row hides a gap."""
    readme = (EVALS_DIR / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `([a-z0-9-]+)` \|", readme, re.MULTILINE))
    actual = {c.name for c in EVAL_CASES}
    missing = sorted(listed - actual)
    assert not missing, f"evals/README.md lists case(s) that do not exist: {missing}"
    assert len(listed) >= 10, (
        f"the adversarial table lists {len(listed)} cases; ten are the point of the suite"
    )


def test_adversarial_cases_are_tagged_as_such() -> None:
    """Tagging is how a runner selects the half that matters."""
    readme = (EVALS_DIR / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `([a-z0-9-]+)` \|", readme, re.MULTILINE))
    for case in EVAL_CASES:
        if case.name not in listed:
            continue
        fields = _frontmatter((case / "prompt.md").read_text(encoding="utf-8"), case / "prompt.md")
        assert "adversarial" in fields["tags"], (
            f"{case.name} is in the adversarial table but not tagged adversarial"
        )


def test_eval_prompts_quote_no_credential_shaped_literals() -> None:
    """`make security` scans every tracked file, and these discuss secrets."""
    patterns = (r"AKIA[0-9A-Z]{16}", r"gh[pousr]_[A-Za-z0-9]{20,}",
                r"github_pat_[A-Za-z0-9_]{20,}", r"sk-[A-Za-z0-9]{20,}",
                r"xox[bpras]-[A-Za-z0-9-]{10,}")
    for path in sorted(EVALS_DIR.glob("**/*.md")):
        body = path.read_text(encoding="utf-8")
        for pattern in patterns:
            assert not re.search(pattern, body), (
                f"{path.relative_to(REPO_ROOT)} matches {pattern!r}; make security scans it"
            )


# --- context7.json ----------------------------------------------------------


def test_context7_config_is_valid_and_its_folders_exist() -> None:
    """A retrieval config scoping a renamed folder indexes nothing, silently."""
    config = json.loads(CONTEXT7.read_text(encoding="utf-8"))
    for key in ("projectTitle", "description", "folders", "excludeFolders"):
        assert key in config, f"context7.json missing {key!r}"
    assert 10 <= len(config["description"]) <= 200, (
        "context7.json description must be between ten and two hundred characters"
    )
    for folder in config["folders"]:
        assert (REPO_ROOT / folder).is_dir(), (
            f"context7.json indexes {folder!r}, which is not a directory"
        )
    for folder in config["excludeFolders"]:
        assert (REPO_ROOT / folder).is_dir(), (
            f"context7.json excludes {folder!r}, which no longer exists; "
            "a stale exclusion silently stops excluding"
        )
    for name in config.get("excludeFiles", []):
        assert (REPO_ROOT / name).exists(), f"context7.json excludes missing file {name!r}"


def test_context7_indexes_the_skill_and_excludes_the_evals() -> None:
    """The scoping decision itself, pinned: skill in, eval prompts out.

    The eval prompts are adversarial instructions ("waive all the findings").
    Indexing them for retrieval would surface those strings to an agent as if
    they were guidance.
    """
    config = json.loads(CONTEXT7.read_text(encoding="utf-8"))
    assert any("skills/" in f for f in config["folders"])
    assert "evals" in config["excludeFolders"]


# --- llms.txt ---------------------------------------------------------------


def test_llms_txt_links_resolve() -> None:
    """Every path it advertises must exist, or the index sends readers nowhere."""
    text = LLMS_TXT.read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+)\)", text)
    assert links, "llms.txt advertises no documents at all"
    missing = [ref for ref in links if not (REPO_ROOT / ref).exists()]
    assert not missing, f"llms.txt links to missing path(s): {missing}"


def test_llms_txt_states_the_exit_code_contract() -> None:
    """It is a summary for agents; omitting the contract makes it misleading."""
    text = LLMS_TXT.read_text(encoding="utf-8")
    for token in ("Exit 0", "Exit 1", "Exit 2"):
        assert token in text, f"llms.txt does not state {token}"


# --- release workflow -------------------------------------------------------


def _workflow_jobs(text: str) -> dict[str, str]:
    """Split a workflow's ``jobs:`` mapping into one text block per job.

    A crude split, but scoped: a top-level ``jobs:`` key, then each two-space
    indented ``<name>:`` starts a block that runs to the next one. That is
    enough to ask "does *this* job declare that dependency" instead of "does
    this string appear anywhere in the file", which a comment or an unrelated
    job would satisfy just as well.

    No YAML parser is used because this project declares no runtime
    dependencies and none is available to the test suite either.
    """
    body = text.split("\njobs:\n", 1)[1] if "\njobs:\n" in text else ""
    assert body, "release.yml has no top-level jobs: mapping"
    jobs: dict[str, str] = {}
    current: str | None = None
    for line in body.splitlines():
        header = re.match(r"^  ([A-Za-z_][\w-]*):\s*$", line)
        if header:
            current = header.group(1)
            jobs[current] = ""
            continue
        if line and not line.startswith("  ") and not line.startswith("\t"):
            break  # dedented out of jobs: entirely
        if current:
            jobs[current] += line + "\n"
    return jobs


def _uncommented(block: str) -> str:
    """Strip comment-only lines and trailing comments before matching.

    Without this, every assertion below is satisfiable by a comment that
    merely mentions the token it is looking for.
    """
    kept = []
    for line in block.splitlines():
        stripped = line.split("#", 1)[0]
        if stripped.strip():
            kept.append(stripped)
    return "\n".join(kept)


def test_release_workflow_is_gated_and_uses_trusted_publishing() -> None:
    """The publish path's own safety properties, pinned per job.

    Scoped to the job blocks rather than the whole file: asserting that
    ``needs: gate`` appears *somewhere* does not pin the wiring at all, since
    a comment or an unrelated job satisfies it identically. The question worth
    asking is whether the publish job depends on the build job, and this asks
    exactly that.
    """
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    jobs = _workflow_jobs(text)
    assert {"gate", "build", "publish"} <= set(jobs), (
        f"release.yml defines jobs {sorted(jobs)}; the gate/build/publish chain is "
        "what makes publishing safe"
    )

    gate, build, publish = (_uncommented(jobs[n]) for n in ("gate", "build", "publish"))

    assert "make pre-pr" in gate, "the gate job must run the full ladder"
    assert re.search(r"^\s*needs:\s*gate\s*$", build, re.MULTILINE), (
        "the build job must depend on the gate job, not run beside it"
    )
    assert "python -m venv" in build, (
        "the clean-environment console-script smoke test is the wheel's only check"
    )
    assert re.search(r"^\s*needs:\s*build\s*$", publish, re.MULTILINE), (
        "the publish job must depend on the build job"
    )
    assert re.search(r"^\s*id-token:\s*write\s*$", publish, re.MULTILINE), (
        "trusted publishing needs an OIDC token, declared on the publish job"
    )
    assert "pypa/gh-action-pypi-publish" in publish

    # No stored secret anywhere: trusted publishing exists so none is needed.
    assert "secrets.PYPI" not in text, "a stored token defeats trusted publishing"
    # Least privilege at the top level.
    assert re.search(r"^permissions:\n\s+contents:\s*read\s*$", text, re.MULTILINE), (
        "the workflow's default permissions must be read-only"
    )


def test_every_workflow_is_scanned_by_the_threshold_guard() -> None:
    """Wiring check: the guard's target list must cover what actually exists."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "nht", REPO_ROOT / "tools" / "check_no_hardcoded_thresholds.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Both spellings GitHub Actions accepts. Globbing only *.yml here would let
    # a workflow added as .yaml escape this wiring check entirely -- the same
    # single-spelling assumption the guard itself was just fixed for.
    on_disk = {p.name for p in WORKFLOWS.glob("*.yml")} | {
        p.name for p in WORKFLOWS.glob("*.yaml")
    }
    scanned = {p.name for p in mod.targets()}
    assert on_disk <= scanned, (
        f"workflow(s) {sorted(on_disk - scanned)} exist but the guard does not "
        "scan them"
    )
    assert on_disk == {"ci.yml", "release.yml"}, (
        f"a workflow was added or renamed ({sorted(on_disk)}); confirm the guard "
        "still globs the directory rather than naming files"
    )
    for name in on_disk:
        assert mod.check_workflow(WORKFLOWS / name) == []


# --- generated artifacts ----------------------------------------------------


@pytest.mark.parametrize(
    "script,target",
    [("render_plugin_manifests.py", "make skill-manifests")],
)
def test_generated_artifacts_are_fresh(script: str, target: str) -> None:
    """Every generated artifact matches its generator on the committed tree.

    The rule catalog is deliberately absent from this list: it has its own
    AC-pinned check (``test_skill_contract.py::test_rule_catalog_is_fresh``,
    verifying AC-SD-2) and running it twice would be duplication, not defence.
    This is parametrized so a future generator is added by one list entry.
    """
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / script), "--check"],
        capture_output=True, text=True, check=False, encoding="utf-8",
    )
    assert result.returncode == 0, (
        f"{result.stdout}{result.stderr}\nrun `{target}` to regenerate"
    )


def test_manifest_generator_rejects_a_folded_description(tmp_path: Path) -> None:
    """A folded scalar must stop the generator, not become the description.

    Written as `description: >-`, a naive parser yields the fold marker itself.
    A published manifest whose description reads ">-" is worse than a build
    failure, so the generator raises instead of defaulting.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "rpm", REPO_ROOT / "tools" / "render_plugin_manifests.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(ValueError):
        mod.skill_description("---\nname: x\ndescription: >-\n  folded text\n---\n\nbody\n")
    with pytest.raises(ValueError):
        mod.skill_description("---\nname: x\n---\n\nbody\n")
    with pytest.raises(ValueError):
        mod.skill_description("no frontmatter at all\n")


def test_manifest_version_tracks_the_package_not_a_literal() -> None:
    """The generator must read the version, never restate it."""
    source = (REPO_ROOT / "tools" / "render_plugin_manifests.py").read_text(encoding="utf-8")
    assert "from openspec_graph import __version__" in source
    assert not re.search(r'"version":\s*"\d+\.\d+', source), (
        "the manifest generator hard-codes a version literal"
    )


# --- packaging surface ------------------------------------------------------


def test_docker_build_context_is_sufficient_for_the_dynamic_version() -> None:
    """The Dockerfile copies a subset; `attr:` needs the package in it.

    `pyproject.toml` reads the version from `openspec_graph.__version__`, so a
    build context missing the package (or the README that `readme =` names)
    fails at install time rather than at review time.
    """
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    copied = re.findall(r"^COPY\s+(.+?)\s+\S+$", dockerfile, re.MULTILINE)
    copied_tokens = {tok for line in copied for tok in line.split()}
    for required in ("pyproject.toml", "openspec_graph"):
        assert required in copied_tokens, (
            f"Dockerfile does not COPY {required!r}, which the build needs"
        )
    readme_declared = 'readme = "README.md"' in (
        REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if readme_declared:
        assert "README.md" in copied_tokens, (
            "pyproject declares readme = README.md but the Dockerfile never copies it"
        )


def test_agent_artifacts_are_excluded_from_the_docker_context() -> None:
    """Prose for external agents has no place in a runtime image."""
    ignored = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for entry in ("skills", "evals", ".claude-plugin", "context7.json", "llms.txt"):
        assert entry in ignored, f".dockerignore does not exclude {entry!r}"
