"""Every install line this repository prints, held to what it actually ships.

The failure this exists for already happened: the project was renamed, the
distribution was renamed with it, and eight places kept printing an install
command for a name that no longer existed -- README, the skill's own preflight
step, and both copies of the CI template an adopter is told to paste into their
repository. Nothing failed, because nothing checks prose against packaging
metadata.

These are text checks, deliberately. A test cannot prove a distribution
resolves on a package index without network access, and a gate that needs the
network is a gate that fails on a plane. What it can prove is that every
install line spells the name this repository actually builds, that the version
floor an adopter is handed is the one the skill enforces, and that the changelog
links to release tags that follow this project's own naming. Publication itself
is a release-time check (`.github/workflows/release.yml` installs the built
wheel into a clean environment), not a unit test.
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
SKILL_ASSET = REPO_ROOT / "skills" / "planlint-spec-governance" / "assets" / "spec-gate.yml"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Files an adopter reads and copies from. Deliberately excludes
# ``openspec/changes/**``: merged change packages are a historical record of
# what was true when they were written, and rewriting history to satisfy a
# lint is how a project loses the ability to explain itself.
ADOPTER_FILES = (README, SKILL_MD, TEMPLATE, SKILL_ASSET)

# Names this project has shipped under, or is confused with. `openspec-graph`
# was the distribution before the rename and no longer exists on any index;
# `plan-lint` is an unrelated project that happens to sit one hyphen away.
_RETIRED_NAME = "openspec-graph"
_COLLIDING_NAME = "plan-lint"

# `pip install <something>` / `pipx install <something>`, capturing the
# requirement specifier so the name and any version bound can be checked apart.
_INSTALL = re.compile(
    r"(?:pip|pipx|uv tool)\s+install\s+(?:--?\S+\s+)*[\"']?([A-Za-z0-9._-]+)"
)


def _distribution_name() -> str:
    """The name in ``pyproject.toml``, read the way a packager would.

    Read by regex rather than by importing metadata: the point is to compare
    prose against the *source of truth in the tree*, which is what a
    contributor edits, not against whatever happens to be installed in the
    environment running the tests.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name = "([^"]+)"$', text, re.MULTILINE)
    assert match, "pyproject.toml has no [project] name"
    return match.group(1)


def _lines(path: Path) -> list[tuple[int, str]]:
    return list(enumerate(path.read_text(encoding="utf-8").splitlines(), start=1))


@pytest.mark.parametrize("path", ADOPTER_FILES, ids=[p.name for p in ADOPTER_FILES])
def test_install_lines_name_the_distribution_this_repo_builds(path: Path) -> None:
    """An install command naming anything else is a command that cannot work."""
    expected = _distribution_name()
    for number, line in _lines(path):
        for name in _INSTALL.findall(line):
            # `pip install -e .` and friends install the checkout, not a name.
            if name.startswith((".", "/")) or name in {"e", "git+https"}:
                continue
            assert name == expected, (
                f"{path.relative_to(REPO_ROOT)}:{number} installs {name!r}, but this "
                f"repository builds {expected!r}: {line.strip()!r}"
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


def test_the_colliding_name_appears_only_where_it_is_disambiguated() -> None:
    """`plan-lint` is somebody else's project; naming it loosely invites the mix-up.

    Allowed only on a line that says so. The check is the disambiguation's own
    regression test: delete the sentence and this fails rather than quietly
    leaving a stray reference that reads like an alternate spelling of ours.
    """
    for path in (README, LLMS_TXT):
        for number, line in _lines(path):
            if _COLLIDING_NAME in line.replace(_RETIRED_NAME, ""):
                assert "unrelated" in line.lower(), (
                    f"{path.relative_to(REPO_ROOT)}:{number} mentions "
                    f"{_COLLIDING_NAME!r} without marking it unrelated: {line.strip()!r}"
                )


def test_ci_template_pins_the_floor_the_skill_enforces() -> None:
    """Two floors, one meaning: the adopter's and the agent's must be one number.

    The template pins a lower bound so a future major with a different
    exit-code contract cannot walk into an adopter's CI. The skill refuses to
    run against a CLI older than its own declared minimum. If those drift, an
    adopter installs a version their agent then rejects.
    """
    frontmatter = SKILL_MD.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    declared = re.search(r"^\s+planlint-min-version:\s*(\S+)$", frontmatter, re.MULTILINE)
    assert declared, "SKILL.md declares no metadata.planlint-min-version"

    pinned = re.search(r'planlint>=([0-9.]+),<\d', TEMPLATE.read_text(encoding="utf-8"))
    assert pinned, "templates/spec-gate.yml no longer pins a planlint lower bound"
    assert pinned.group(1) == declared.group(1), (
        f"the CI template installs planlint>={pinned.group(1)} but the skill requires "
        f"{declared.group(1)}; an adopter would install a CLI their agent refuses"
    )


def test_changelog_links_this_version_to_its_release_tag() -> None:
    """A changelog link that 404s is worse than no link: it implies a release."""
    text = CHANGELOG.read_text(encoding="utf-8")
    for version in (__version__, "0.1.0"):
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

    match = re.search(r"^/plugin install (\S+)@(\S+)\s*$", readme, re.MULTILINE)
    assert match, "README.md no longer shows a `/plugin install` command"
    assert (match.group(1), match.group(2)) == (plugin, marketplace), (
        f"README installs {match.group(1)}@{match.group(2)} but the manifests declare "
        f"{plugin}@{marketplace}"
    )
    assert "/plugin marketplace add ianshank/planlint" in readme, (
        "README.md no longer shows the marketplace-add command that must precede it"
    )
