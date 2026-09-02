"""Deterministic validation of `.claude/agents/*.md` and
`.claude/skills/**/*.md` -- the Claude Code dev-tooling used to develop
this repo itself, not `planlint`'s own product code (see
`docs/agents-skills-harness.md`'s disambiguation note).

Mirrors `test_rule_registry_docs.py`'s own reason for existing: nothing
previously caught `.claude/skills/planlint-add-rule/SKILL.md`'s rule-family
list silently missing `rules_speckit.py` after the SpecKit dialect (a real,
found-in-review drift instance, not a hypothetical). These files are prose
read by an agent, not code exercised by the test suite -- with nothing
checking them, a stale command, a renamed test file, or a dropped rule
family drifts silently and is only caught if a human (or another agent)
happens to notice.

Pure: reads `.claude/` files and `Makefile`/`rules.py` as plain text; no
CLI/subprocess needed (mirrors `test_rule_registry_docs.py`'s own style).
No new dependency -- frontmatter is flat `key: value` pairs, parsed with a
plain line split rather than pulling in PyYAML (`dependencies = []` in
`pyproject.toml` is a load-bearing product boundary; see `docs/hooks.md`'s
"Adding a new pure derived-output module" convention, which this test
follows for its own parsing).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))
SKILL_FILES = sorted(SKILLS_DIR.glob("**/*.md"))
ALL_FILES = AGENT_FILES + SKILL_FILES

# A backtick span that looks like a real repo-relative file path: only
# path-safe characters (no `<`/`>` template placeholders, no `*` globs, no
# spaces/parens that would mean it's a code snippet or CLI invocation),
# ending in a recognized extension, or the bare filenames referenced by
# name with no extension.
_PATH_LIKE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|toml|json|ya?ml|sh)|Makefile)`")

# A single backtick span that is exactly `make <target>` -- deliberately
# anchored to start with "make " so a template placeholder like
# "`**Gate:** make X`" (spec-drafter.md's own instructions to *write* that
# literal string into a future tasks.md) never matches.
_MAKE_TARGET_REF = re.compile(r"`make ([a-z][a-z-]*)`")

_MAKEFILE_TARGETS = set(
    re.findall(r"^([a-zA-Z_-]+):", (REPO_ROOT / "Makefile").read_text(encoding="utf-8"), re.MULTILINE)
)

# Directories excluded from the "does this real file exist anywhere in the
# repo" fallback below -- generated/cache/VCS content, never a legitimate
# doc-reference target.
_IGNORED_DIR_PARTS = {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "htmlcov"}
_ALL_BASENAMES = {
    p.name
    for p in REPO_ROOT.rglob("*")
    if p.is_file() and not _IGNORED_DIR_PARTS.intersection(p.relative_to(REPO_ROOT).parts)
}


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the flat `key: value` YAML frontmatter between the leading
    `---` markers. Not a general YAML parser -- these files only ever use
    single-line scalar values, verified by reading all of them."""
    assert text.startswith("---\n"), "frontmatter must open with '---' on the first line"
    end = text.index("\n---\n", 4)
    block = text[4:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in paths]


def test_at_least_one_agent_and_one_skill_file_exist() -> None:
    # A silently-empty glob would make every other test in this file
    # vacuously pass -- assert real content is actually being checked.
    assert AGENT_FILES, f"no agent files found under {AGENTS_DIR}"
    assert SKILL_FILES, f"no skill files found under {SKILLS_DIR}"


@pytest.mark.parametrize("path", AGENT_FILES, ids=_ids(AGENT_FILES))
def test_agent_frontmatter_has_required_keys(path: Path) -> None:
    fields = _frontmatter(path.read_text(encoding="utf-8"))
    for key in ("name", "description", "tools"):
        assert fields.get(key), f"{path.name}: frontmatter missing/empty {key!r}"
    assert fields["name"] == path.stem, (
        f"{path.name}: frontmatter name {fields['name']!r} doesn't match filename stem {path.stem!r}"
    )


@pytest.mark.parametrize("path", SKILL_FILES, ids=_ids(SKILL_FILES))
def test_skill_frontmatter_has_required_keys(path: Path) -> None:
    fields = _frontmatter(path.read_text(encoding="utf-8"))
    for key in ("name", "description"):
        assert fields.get(key), f"{path.name}: frontmatter missing/empty {key!r}"


def _reference_resolves(ref: str) -> bool:
    # A `/`-qualified reference must resolve from the repo root exactly, as
    # written -- that's the whole point of checking it. A bare filename
    # (no `/`) is legitimate shorthand once a file/directory has already
    # been named in surrounding prose (e.g. "`tools/check_coverage_floor.py`/
    # `check_branch_coverage.py`"), so it only needs to exist *somewhere* in
    # the repo, not at exactly this spot.
    if "/" in ref:
        return (REPO_ROOT / ref).exists()
    return ref in _ALL_BASENAMES


@pytest.mark.parametrize("path", ALL_FILES, ids=_ids(ALL_FILES))
def test_path_like_backtick_references_resolve_to_real_files(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    referenced = sorted(set(_PATH_LIKE.findall(text)))
    missing = [ref for ref in referenced if not _reference_resolves(ref)]
    assert not missing, (
        f"{path.relative_to(REPO_ROOT)} references path(s) that don't exist in the repo: {missing}"
    )


@pytest.mark.parametrize("path", ALL_FILES, ids=_ids(ALL_FILES))
def test_make_target_references_are_real_makefile_targets(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    referenced = sorted(set(_MAKE_TARGET_REF.findall(text)))
    unknown = [t for t in referenced if t not in _MAKEFILE_TARGETS]
    assert not unknown, (
        f"{path.relative_to(REPO_ROOT)} references make target(s) not in the Makefile: {unknown} "
        f"(known targets: {sorted(_MAKEFILE_TARGETS)})"
    )


def test_add_rule_skill_rule_family_list_matches_real_rule_modules() -> None:
    # The exact drift class this test file exists to close: this skill's
    # own step-1 checklist silently omitted rules_speckit.py after the
    # SpecKit dialect added it, caught only by a manual review pass.
    skill_path = SKILLS_DIR / "planlint-add-rule" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    real_families = {
        p.stem for p in (REPO_ROOT / "openspec_graph").glob("rules_*.py")
    }
    referenced_families = set(re.findall(r"`(rules_[a-z]+)\.py`", text))
    assert referenced_families == real_families, (
        f"{skill_path.relative_to(REPO_ROOT)}'s rule-family checklist is out of sync with "
        f"openspec_graph/rules_*.py.\nmissing/extra: {real_families ^ referenced_families}"
    )
