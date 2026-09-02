"""Every install line this repository prints, held to what it actually ships.

The failure this exists for already happened: the project was renamed, the
distribution was renamed with it, and eight places kept printing an install
command for a name that no longer existed -- README, the skill's own preflight
step, and both copies of the CI template an adopter is told to paste into their
repository. Nothing failed, because nothing compares prose against packaging
metadata.

These are text checks, deliberately. A test cannot prove a distribution
resolves on a package index without network access, and a gate that needs the
network is a gate that fails on a plane. What it can prove is that every
install line spells the name this repository actually builds, that the version
floor an adopter is handed is the one the skill enforces, and that the changelog
links releases the way this project names them. Publication itself is a
release-time check (`.github/workflows/release.yml` installs the built wheel
into a clean environment), not a unit test.

Two design choices are load-bearing, because the first draft of this file got
both wrong and a review caught them:

*Files are discovered, not listed.* The incident was eight places drifting; a
hand-written tuple of the four that were fixed is a regression test for those
four, not a gate against a ninth. So the corpus is globbed.

*Every scan asserts its own subject exists.* A loop over matches that finds no
matches passes, which turns "this text must say X" into "this text must not say
not-X" -- the check evaporates exactly when someone deletes the thing it
guards.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from openspec_graph import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
LLMS_TXT = REPO_ROOT / "llms.txt"
SKILL_MD = REPO_ROOT / "skills" / "planlint-spec-governance" / "SKILL.md"
TEMPLATE = REPO_ROOT / "templates" / "spec-gate.yml"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Directories whose contents are a historical record rather than instructions.
# A merged change package describes what was true when it was written, and
# rewriting history to satisfy a lint is how a project loses the ability to
# explain itself. Everything else that a human or an agent might copy from is
# in scope.
_EXCLUDED_DIRS = ("openspec", ".git", ".venv", "node_modules", "evals")

_COLLIDING_NAME = "plan-lint"

# pip flags that consume the following token, which would otherwise be read as
# the package name. `-r requirements.txt` is the one that actually appears in
# the wild; the rest are here so an enterprise adopter's `--index-url` line
# does not fail this suite for the wrong reason.
_VALUE_FLAGS = frozenset({
    "-r", "--requirement", "-c", "--constraint", "-i", "--index-url",
    "--extra-index-url", "-f", "--find-links", "-t", "--target",
    "--prefix", "--root", "--python", "--proxy", "--cert", "--client-cert",
})

# `pip install`, `pip3 install`, `python -m pip install`, `uv pip install`,
# `pipx install`, `uv tool install`. Captures everything after the verb so the
# argument vector can be walked properly -- a single regex cannot both skip
# value-taking flags and capture the first positional.
_INSTALL_COMMAND = re.compile(r"\b(?:pip[0-9]*|pipx|uv tool|uv pip)\s+install\s+(?P<rest>.*)")


def _requirements(line: str) -> list[str]:
    """Distribution names an install line names, ignoring everything that is not one.

    Walks the argument vector rather than pattern-matching the package
    position, because the things that are *not* a distribution name -- flags,
    flags with values, VCS URLs, requirement files, local paths -- are exactly
    what a naive regex captures and then has to be exempted from one by one.
    Returns the bare project names, with extras and version specifiers removed.
    """
    names: list[str] = []
    for match in _INSTALL_COMMAND.finditer(line):
        tokens = match.group("rest").split()
        skip_next = False
        for raw in tokens:
            if skip_next:
                skip_next = False
                continue
            # Install commands appear inside prose as often as in code fences,
            # so a token can arrive wrapped in markdown: `pip install foo`),
            # "foo", 'foo'. Quotes and backticks are stripped from both ends;
            # sentence punctuation only from the right. The asymmetry matters:
            # stripping a leading "." would turn the local-path install
            # `pip install -e .` into an empty token and then read the next
            # English word as a distribution name.
            token = raw.strip("\"'`").rstrip("\"'`),.;:|")
            if not token:
                continue
            if token in _VALUE_FLAGS:
                skip_next = True
                continue
            if token.startswith("-"):
                continue  # a boolean flag, or `--flag=value`
            # Not a distribution: a VCS or direct URL, a local path, or a
            # requirements file. Each is a legitimate install form that names
            # no project on an index.
            if "://" in token or token.startswith(("git+", ".", "/", "~")):
                break
            if token.endswith((".txt", ".whl", ".tar.gz")) or "*" in token:
                break
            # `planlint[dev]>=0.2.0,<1` -> `planlint`
            name = re.split(r"[\[<>=!~;]", token, maxsplit=1)[0]
            if name:
                names.append(name)
            break  # the first positional is the requirement; the rest is noise
    return names


def _distribution_name() -> str:
    """The name under ``[project]`` in pyproject.toml, read section-aware.

    A bare ``^name = "..."`` search returns the first such line in file order
    with no notion of which table it sits under, so a ``name`` key added to any
    ``[tool.*]`` section above ``[project]`` would silently redirect every
    assertion in this module to the wrong string. Tracking the section header
    is the same approach ``tools/check_coverage_floor.py`` already takes for
    ``fail_under``.
    """
    section = None
    for line in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            continue
        if section == "[project]":
            match = re.match(r'name\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    raise AssertionError("pyproject.toml has no name under [project]")


def _adopter_files() -> list[Path]:
    """Every tracked file a reader might copy an install command out of."""
    found: list[Path] = []
    for pattern in ("*.md", "docs/**/*.md", "skills/**/*.md", "skills/**/*.yml",
                    "templates/*.yml", "Dockerfile"):
        for path in REPO_ROOT.glob(pattern):
            if path.is_file() and not any(part in _EXCLUDED_DIRS for part in path.parts):
                found.append(path)
    return sorted(set(found))


ADOPTER_FILES = _adopter_files()


def _lines(path: Path) -> list[tuple[int, str]]:
    return list(enumerate(path.read_text(encoding="utf-8").splitlines(), start=1))


def test_the_adopter_corpus_is_discovered_and_not_empty() -> None:
    """The globs above must actually find the files the rest of this module scans."""
    assert len(ADOPTER_FILES) >= 5, (
        f"only {len(ADOPTER_FILES)} adopter file(s) discovered; the globs have "
        "drifted from the tree and every scan below is now nearly vacuous"
    )
    for required in (README, SKILL_MD, TEMPLATE):
        assert required in ADOPTER_FILES, f"{required.name} is not in the discovered corpus"


def test_the_corpus_actually_prints_install_commands_for_this_project() -> None:
    """Guards every install scan below against passing on an empty match set.

    Counts install lines naming *this* distribution specifically. A count of
    all install commands would stay healthy on `pip install pre-commit` alone,
    which is precisely the state where the scans below have gone blind.
    """
    expected = _distribution_name()
    ours = [
        (path.name, number, line.strip())
        for path in ADOPTER_FILES
        for number, line in _lines(path)
        if expected in _requirements(line)
    ]
    assert len(ours) >= 3, (
        f"found {len(ours)} install command(s) for {expected!r} across the adopter "
        "corpus; the parser has stopped recognizing them, so the scans below "
        f"prove nothing. Matched: {ours}"
    )


# The pre-rename distribution. It exists on no index, so an install line
# naming it is dead, but prose may still mention it as migration advice.
_RETIRED_NAME = "openspec-graph"


def _confusable(name: str) -> str:
    """Fold the spellings a package index treats as distinct but a reader does not."""
    return name.lower().replace("-", "").replace("_", "").replace(".", "")


@pytest.mark.parametrize("path", ADOPTER_FILES, ids=[p.name for p in ADOPTER_FILES])
def test_install_lines_spell_this_project_the_way_it_is_published(path: Path) -> None:
    """An install command for *this* project must name the distribution it builds.

    Scoped to names confusable with ours -- the retired `openspec-graph`, the
    unrelated `plan-lint`, and any hyphen or case variant of `planlint`. Third
    party installs are none of this test's business: `pip install pre-commit`
    in a contributor guide is correct, and a check that demanded every install
    line name this project would fail on it, which is how a test earns a
    blanket ignore and stops being read.
    """
    expected = _distribution_name()
    confusable_with_ours = {_confusable(expected), _confusable(_RETIRED_NAME),
                            _confusable(_COLLIDING_NAME)}
    for number, line in _lines(path):
        for name in _requirements(line):
            if _confusable(name) not in confusable_with_ours:
                continue  # somebody else's package; not this test's subject
            assert name == expected, (
                f"{path.relative_to(REPO_ROOT)}:{number} installs {name!r}, but this "
                f"repository publishes {expected!r}: {line.strip()!r}"
            )


@pytest.mark.parametrize("path", ADOPTER_FILES, ids=[p.name for p in ADOPTER_FILES])
def test_adopter_files_do_not_install_from_the_old_repository_url(path: Path) -> None:
    """The repository moved; a `git+` URL naming the old one installs nothing.

    Scoped to install URLs, not to the old name as a word. `pip uninstall
    openspec-graph` is correct migration advice, and naming the pre-rename
    distribution when dating a historical result is how a receipt stays
    checkable -- neither is drift. A `git+https://.../OpenSpec-Graph` URL is,
    because it is an instruction that fails.
    """
    for number, line in _lines(path):
        assert "github.com/ianshank/OpenSpec-Graph" not in line, (
            f"{path.relative_to(REPO_ROOT)}:{number} installs from the old repository "
            f"URL: {line.strip()!r}"
        )


@pytest.mark.parametrize("path", (README, LLMS_TXT), ids=["README.md", "llms.txt"])
def test_the_colliding_name_is_present_and_marked_unrelated(path: Path) -> None:
    """`plan-lint` is somebody else's project; naming it loosely invites the mix-up.

    Asserts presence first. A scan that only checks the lines it finds passes
    when it finds none, so without the floor this test would go quiet the
    moment someone deleted the disambiguation -- which is the case it exists to
    catch, not an edge of it.
    """
    hits = [(n, line) for n, line in _lines(path) if _COLLIDING_NAME in line]
    assert hits, (
        f"{path.name} no longer mentions {_COLLIDING_NAME!r} at all; the "
        "disambiguation was deleted and readers are back to guessing"
    )
    for number, line in hits:
        assert "unrelated" in line.lower(), (
            f"{path.relative_to(REPO_ROOT)}:{number} mentions {_COLLIDING_NAME!r} "
            f"without marking it unrelated: {line.strip()!r}"
        )


def test_ci_template_pins_the_floor_the_skill_enforces() -> None:
    """Two floors, one meaning: the adopter's and the agent's must be one number.

    The template pins a lower bound so a future major with a different
    exit-code contract cannot walk into an adopter's CI. The skill refuses to
    run against a CLI older than its own declared minimum. If those drift, an
    adopter installs a version their agent then rejects.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    _, fence, body = text.partition("\n---\n")
    assert fence, "SKILL.md has no closing frontmatter fence; the scan below would "
    frontmatter = text[: len(text) - len(body) - len(fence)]
    declared = re.search(r"^[ \t]+planlint-min-version:[ \t]*(\S+)$", frontmatter, re.MULTILINE)
    assert declared, "SKILL.md declares no indented metadata.planlint-min-version"

    pinned = re.search(r"planlint>=([0-9.]+),<\d", TEMPLATE.read_text(encoding="utf-8"))
    assert pinned, "templates/spec-gate.yml no longer pins a planlint lower bound"
    assert pinned.group(1) == declared.group(1), (
        f"the CI template installs planlint>={pinned.group(1)} but the skill requires "
        f"{declared.group(1)}; an adopter would install a CLI their agent refuses"
    )


def test_every_changelog_version_links_to_its_release_tag() -> None:
    """Each released version gets a link definition, and they all point at tags.

    Derived from the changelog's own section headings rather than a hand-kept
    list, which would stop covering 0.2.0 the moment 0.3.0 arrived.

    This asserts the link *shape*, not that the tag resolves. The newest
    section is by definition unreleased while it is being written -- its link
    is a promise the release workflow keeps when the tag is pushed -- so a test
    that demanded a live URL would forbid writing a changelog entry before
    tagging, which is backwards.
    """
    text = CHANGELOG.read_text(encoding="utf-8")
    versions = re.findall(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", text, re.MULTILINE)
    assert versions, "CHANGELOG.md has no versioned sections"
    assert __version__ in versions, (
        f"CHANGELOG.md has no section for the current version {__version__}"
    )
    for version in versions:
        expected = f"[{version}]: https://github.com/ianshank/planlint/releases/tag/v{version}"
        assert expected in text, (
            f"CHANGELOG.md does not link {version} to its release tag; expected a "
            f"line reading {expected!r}"
        )


def test_readme_plugin_commands_match_the_generated_manifests() -> None:
    """The two lines a user pastes to install the plugin, checked against it.

    The manifests are generated, so their names cannot drift from the package.
    The README's install commands are hand-written and can, and a wrong plugin
    id fails at the user's prompt with nothing here to catch it first.
    """
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))["name"]
    marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))["name"]
    readme = README.read_text(encoding="utf-8")

    installs = re.findall(r"^/plugin install (\S+)@(\S+)\s*$", readme, re.MULTILINE)
    assert installs, "README.md no longer shows a `/plugin install` command"
    for found_plugin, found_marketplace in installs:
        assert (found_plugin, found_marketplace) == (plugin, marketplace), (
            f"README installs {found_plugin}@{found_marketplace} but the manifests "
            f"declare {plugin}@{marketplace}"
        )
    assert f"/plugin marketplace add ianshank/{marketplace}" in readme, (
        "README.md no longer shows the marketplace-add command that must precede it"
    )
