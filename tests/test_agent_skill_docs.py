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

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# The distributable Agent Skill published from this repo (skills/) is product,
# not contributor tooling -- but it is prose read by an agent exactly like the
# files under .claude/, so it drifts exactly the same way and is guarded here
# rather than in a second, parallel test file (R-SD-7).
DIST_SKILLS_DIR = REPO_ROOT / "skills"

AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))
DEV_SKILL_FILES = sorted(SKILLS_DIR.glob("**/*.md"))
DIST_SKILL_FILES = sorted(DIST_SKILLS_DIR.glob("**/*.md"))
SKILL_FILES = DEV_SKILL_FILES + DIST_SKILL_FILES
ALL_FILES = AGENT_FILES + SKILL_FILES

# Only a SKILL.md carries frontmatter. A skill's bundled reference documents
# are ordinary markdown the skill body points at, so they are checked for
# path/make-target drift like every other file here but not for frontmatter.
SKILL_MANIFESTS = [p for p in SKILL_FILES if p.name == "SKILL.md"]

# Frontmatter keys whose value is a nested block rather than a scalar. Only
# `metadata` qualifies today; see _frontmatter's own docstring.
_NESTED_KEYS = frozenset({"metadata"})

# The Agent Skills format's own documented limits.
_MAX_DESCRIPTION = 1024
_MAX_COMPATIBILITY = 500

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

def _repo_controlled_basenames(root: Path) -> set[str]:
    """Every filename under ``root``, excluding VCS/cache/build/environment
    directories -- pruned *before* descending (``os.walk``'s ``dirnames[:]
    =`` in-place-filter idiom), not filtered after an unbounded
    ``Path.rglob("*")`` walk already visited them.

    Matters for two reasons, not just speed: an unpruned walk descends into
    a local ``.venv``/``venv``/``env`` (can hold thousands of files, slowing
    collection on every contributor's machine) and, worse, a vendored
    package inside it could ship a file whose *basename* happens to match a
    bare-filename reference in a doc under test -- silently validating a
    reference that isn't actually satisfied by anything this repo controls.
    """
    ignored_dirs = {
        ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "htmlcov",
        ".venv", "venv", "env", "build", "dist", ".idea", ".vscode",
    }
    names: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in ignored_dirs and not d.endswith(".egg-info")
        ]
        names.update(filenames)
    return names


# Every file this repo actually controls -- see _repo_controlled_basenames()
# for why this must prune before descending, not filter after.
_ALL_BASENAMES = _repo_controlled_basenames(REPO_ROOT)


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the `key: value` YAML frontmatter between the leading `---`
    markers, flattening one level of nesting as ``parent.child``.

    Still not a general YAML parser, deliberately: every value stays a
    single-line scalar (DEC-SD-005). That matters more than it looks. A
    folded scalar (``description: >-`` followed by indented prose) would
    parse here as the literal value ``">-"`` -- truthy, so a
    required-key assertion passes, and short, so a length assertion passes
    too, while measuring nothing at all. Keeping the parser flat and the
    files flat means both checks measure real content.

    One level of nesting is supported because the Agent Skills format's
    ``metadata`` key is a map by specification, so a distributable SKILL.md
    cannot express it as a scalar. Deeper nesting is rejected rather than
    silently mis-parsed.
    """
    assert text.startswith("---\n"), "frontmatter must open with '---' on the first line"
    end = text.index("\n---\n", 4)
    block = text[4:end]
    fields: dict[str, str] = {}
    parent: str | None = None
    for line in block.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, _, value = line.strip().partition(":")
        key = key.strip()
        value = value.strip()
        if indent == 0:
            parent = key if (not value and key in _NESTED_KEYS) else None
            if value or key not in _NESTED_KEYS:
                fields[key] = value
            continue
        assert parent is not None, (
            f"indented frontmatter line {line!r} has no nestable parent key; "
            f"only {sorted(_NESTED_KEYS)} may nest"
        )
        fields[f"{parent}.{key}"] = value
    return fields


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in paths]


def test_at_least_one_agent_and_one_skill_file_exist() -> None:
    # A silently-empty glob would make every other test in this file
    # vacuously pass -- assert real content is actually being checked.
    assert AGENT_FILES, f"no agent files found under {AGENTS_DIR}"
    assert DEV_SKILL_FILES, f"no skill files found under {SKILLS_DIR}"
    assert DIST_SKILL_FILES, f"no skill files found under {DIST_SKILLS_DIR}"


@pytest.mark.parametrize("path", AGENT_FILES, ids=_ids(AGENT_FILES))
def test_agent_frontmatter_has_required_keys(path: Path) -> None:
    fields = _frontmatter(path.read_text(encoding="utf-8"))
    for key in ("name", "description", "tools"):
        assert fields.get(key), f"{path.name}: frontmatter missing/empty {key!r}"
    assert fields["name"] == path.stem, (
        f"{path.name}: frontmatter name {fields['name']!r} doesn't match filename stem {path.stem!r}"
    )


@pytest.mark.parametrize("path", SKILL_MANIFESTS, ids=_ids(SKILL_MANIFESTS))
def test_skill_frontmatter_has_required_keys(path: Path) -> None:
    fields = _frontmatter(path.read_text(encoding="utf-8"))
    for key in ("name", "description"):
        assert fields.get(key), f"{path.name}: frontmatter missing/empty {key!r}"


@pytest.mark.parametrize("path", SKILL_MANIFESTS, ids=_ids(SKILL_MANIFESTS))
def test_skill_frontmatter_name_matches_directory_name(path: Path) -> None:
    """AC-SD-1: the format requires `name` to equal the skill's directory."""
    fields = _frontmatter(path.read_text(encoding="utf-8"))
    assert fields["name"] == path.parent.name, (
        f"{path.relative_to(REPO_ROOT)}: frontmatter name {fields['name']!r} "
        f"doesn't match its directory name {path.parent.name!r}"
    )


@pytest.mark.parametrize("path", SKILL_MANIFESTS, ids=_ids(SKILL_MANIFESTS))
def test_skill_frontmatter_fields_are_within_format_limits(path: Path) -> None:
    """AC-SD-1: length limits the Agent Skills format imposes.

    Meaningful only because _frontmatter refuses folded scalars -- see its
    docstring for why a folded value would make this assertion vacuous.
    """
    fields = _frontmatter(path.read_text(encoding="utf-8"))
    assert len(fields["description"]) <= _MAX_DESCRIPTION, (
        f"{path.relative_to(REPO_ROOT)}: description is "
        f"{len(fields['description'])} chars, over the {_MAX_DESCRIPTION} limit"
    )
    compat = fields.get("compatibility", "")
    assert len(compat) <= _MAX_COMPATIBILITY, (
        f"{path.relative_to(REPO_ROOT)}: compatibility is {len(compat)} chars, "
        f"over the {_MAX_COMPATIBILITY} limit"
    )
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"]), (
        f"{path.relative_to(REPO_ROOT)}: name {fields['name']!r} must be "
        "lowercase alphanumerics separated by single hyphens"
    )


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


def _reference_resolves_for(doc: Path, ref: str) -> bool:
    """As :func:`_reference_resolves`, but also accepting a path relative to
    ``doc``'s own directory.

    A distributable skill addresses its own bundled files the way its
    consumers will read them -- ``references/rule-catalog.md``, not
    ``skills/planlint-spec-governance/references/rule-catalog.md`` -- because
    the directory is copied wholesale into another agent's skills folder and
    the repo-root prefix is meaningless there. Both the document's own
    directory and the enclosing skill root (the nearest ancestor holding a
    SKILL.md) are accepted, since a reference document naturally addresses a
    sibling the same way the skill body does. Repo-root resolution is still
    tried first, so nothing about the existing .claude/ files changes.
    """
    if _reference_resolves(ref):
        return True
    if (doc.parent / ref).exists():
        return True
    for ancestor in doc.parents:
        if (ancestor / "SKILL.md").exists():
            return (ancestor / ref).exists()
        if ancestor == REPO_ROOT:
            break
    return False


@pytest.mark.parametrize("path", ALL_FILES, ids=_ids(ALL_FILES))
def test_path_like_backtick_references_resolve_to_real_files(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    referenced = sorted(set(_PATH_LIKE.findall(text)))
    missing = [ref for ref in referenced if not _reference_resolves_for(path, ref)]
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


# --- AC-SD-8 / AC-SD-9: the guard's own new machinery -----------------------


def test_frontmatter_parses_one_nested_level() -> None:
    """AC-SD-9 (non-success): a nested value parses as itself, not a marker.

    The regression this pins is subtle and was found in review rather than in
    a failing test: written as a folded scalar (``description: >-`` plus
    indented prose), the value parses as the literal ``">-"``. That is truthy,
    so a required-key check passes, and two characters long, so a length check
    passes -- both while measuring nothing. Asserting the nested form parses
    correctly is what keeps those other assertions meaningful.
    """
    parsed = _frontmatter(
        "---\n"
        "name: demo-skill\n"
        "description: one line, stays a scalar\n"
        "metadata:\n"
        "  version: 1.2.3\n"
        "  planlint-min-version: 0.2.0\n"
        "---\n\nbody\n"
    )
    assert parsed["name"] == "demo-skill"
    assert parsed["description"] == "one line, stays a scalar"
    assert parsed["metadata.version"] == "1.2.3"
    assert parsed["metadata.planlint-min-version"] == "0.2.0"
    assert "metadata" not in parsed, "a nested parent must not also land as a scalar"


def test_frontmatter_rejects_nesting_under_an_unnestable_key() -> None:
    """Deeper or unexpected nesting fails loudly rather than mis-parsing."""
    with pytest.raises(AssertionError):
        _frontmatter("---\nname: demo\n  stray: value\n---\n\nbody\n")


def test_skill_relative_references_resolve() -> None:
    """AC-SD-8: a skill addresses its own files the way its consumers do.

    ``references/rule-catalog.md`` must resolve from the skill root even
    though no such path exists from the repo root -- the directory is copied
    wholesale into another agent's skills folder, where a repo-root prefix
    would be meaningless.
    """
    skill_md = DIST_SKILLS_DIR / "planlint-spec-governance" / "SKILL.md"
    assert skill_md.exists()
    for ref in ("references/rule-catalog.md", "references/exit-codes.md",
                "references/dialects.md", "assets/spec-gate.yml"):
        assert not (REPO_ROOT / ref).exists(), (
            f"{ref} resolves from the repo root, so this test proves nothing"
        )
        assert _reference_resolves_for(skill_md, ref), (
            f"{ref} does not resolve relative to the skill root"
        )


def test_skill_min_version_is_not_ahead_of_the_package() -> None:
    """A skill demanding a version this repo has not shipped is unusable."""
    from openspec_graph import __version__

    def _tuple(v: str) -> tuple[int, ...]:
        return tuple(int(part) for part in v.split(".") if part.isdigit())

    for path in SKILL_MANIFESTS:
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        required = fields.get("metadata.planlint-min-version")
        if not required:
            continue
        assert _tuple(required) <= _tuple(__version__), (
            f"{path.relative_to(REPO_ROOT)} requires planlint {required}, "
            f"but this tree is {__version__}"
        )


def test_rule_ids_cited_by_skills_exist_in_the_registry() -> None:
    """A skill citing a rule the engine dropped is worse than citing none."""
    from openspec_graph.rules import RULES

    known = {rule.ident for rule in RULES}
    for path in DIST_SKILL_FILES:
        cited = set(re.findall(r"\b([GHUSW]\d{3})\b", path.read_text(encoding="utf-8")))
        unknown = sorted(cited - known)
        assert not unknown, (
            f"{path.relative_to(REPO_ROOT)} cites rule id(s) not in the registry: {unknown}"
        )
