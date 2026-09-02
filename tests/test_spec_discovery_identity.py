"""One spec on disk is discovered once, however many paths reach it.

`Path.glob()` follows a *valid* directory symlink, so a
`specs/002-alias -> specs/001-foo` link yields two distinct `Path` entries for
the same `spec.md`. Unfixed, one spec is parsed twice: `change_dirs` and
`feature_dirs` over-count, `validate`'s `specs_checked` over-reports, and
`build_graph` renders duplicate `FR-001`/`SC-001` nodes for a single
requirement — a spec graph that shows work that does not exist.

Both discovery functions are covered. The bug was found in the SpecKit path
during review of that dialect, but `find_spec_files` had the identical latent
behaviour for `openspec/changes/`, which is why the fix is one shared helper
rather than a dialect-specific patch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openspec_graph import detect
from tests.support import run_cli, supports_symlinks, write_spec, write_speckit_spec

FX = Path(__file__).resolve().parent / "fixtures"

pytestmark = pytest.mark.skipif(
    not supports_symlinks(),
    reason="creating a symlink needs privileges this platform withholds",
)


def _machinery(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "pyproject.toml").write_text(
        (FX / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )


# --- The helper itself ---


def test_dedupe_keeps_one_entry_per_underlying_file(tmp_path: Path) -> None:
    real = tmp_path / "real.md"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(real)

    assert detect._dedupe_by_identity([real, link]) == [real]


def test_dedupe_prefers_the_real_path_over_an_alias(tmp_path: Path) -> None:
    """The survivor must be the name a reviewer would recognise.

    Keeping the first entry in sorted order was deterministic but arbitrary,
    and measurably wrong: with `changes/alias -> changes/real`, "alias" sorts
    first, so the real package became unaddressable by its own name. The
    alias is listed first here precisely so ordering cannot supply the right
    answer by accident.
    """
    real = tmp_path / "real.md"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "alias.md"
    link.symlink_to(real)

    assert detect._dedupe_by_identity([link, real]) == [real]


def test_dedupe_is_stable_when_neither_candidate_is_the_real_path(
    tmp_path: Path,
) -> None:
    """Two aliases pointing at a file outside the scanned set: no candidate
    is the real path, so ordering decides and the result stays stable."""
    real = tmp_path / "outside" / "real.md"
    real.parent.mkdir()
    real.write_text("x", encoding="utf-8")
    first = tmp_path / "a-alias.md"
    second = tmp_path / "b-alias.md"
    first.symlink_to(real)
    second.symlink_to(real)

    assert detect._dedupe_by_identity([first, second]) == [first]
    assert detect._dedupe_by_identity([second, first]) == [second]


def test_dedupe_keeps_genuinely_distinct_files_with_identical_content(
    tmp_path: Path,
) -> None:
    """Non-success criterion: identity is the file, not its bytes. Two real
    specs that happen to read the same are two specs, and collapsing them
    would silently drop one from every gate."""
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("identical", encoding="utf-8")
    second.write_text("identical", encoding="utf-8")

    assert detect._dedupe_by_identity([first, second]) == [first, second]


def test_dedupe_is_a_no_op_without_links(tmp_path: Path) -> None:
    paths = []
    for name in ("a.md", "b.md", "c.md"):
        path = tmp_path / name
        path.write_text("x", encoding="utf-8")
        paths.append(path)

    assert detect._dedupe_by_identity(paths) == paths


# --- OpenSpec discovery ---


def test_a_symlinked_change_package_is_discovered_once(tmp_path: Path) -> None:
    repo = tmp_path
    _machinery(repo)
    write_spec(repo, "real-change", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    changes = repo / "openspec" / "changes"
    (changes / "alias-change").symlink_to(changes / "real-change", target_is_directory=True)

    found = detect.find_spec_files(repo / "openspec")

    assert len(found) == 1, [str(p) for p in found]


def test_profile_does_not_double_count_change_dirs(tmp_path: Path) -> None:
    repo = tmp_path
    _machinery(repo)
    write_spec(repo, "real-change", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    changes = repo / "openspec" / "changes"
    (changes / "alias-change").symlink_to(changes / "real-change", target_is_directory=True)

    profile = detect.profile(repo)

    assert len(profile.change_dirs) == 1, [str(d) for d in profile.change_dirs]


def test_validate_reports_one_spec_checked(tmp_path: Path) -> None:
    repo = tmp_path
    _machinery(repo)
    write_spec(repo, "real-change", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    changes = repo / "openspec" / "changes"
    (changes / "alias-change").symlink_to(changes / "real-change", target_is_directory=True)

    payload = json.loads(run_cli(repo, "validate", "--json").stdout)

    assert payload["specs_checked"] == 1


# --- SpecKit discovery ---


def test_a_symlinked_feature_is_discovered_once(tmp_path: Path) -> None:
    repo = tmp_path
    _machinery(repo)
    write_speckit_spec(repo, "001-real", (FX / "good_speckit.md").read_text(encoding="utf-8"))
    specs = repo / "specs"
    (specs / "002-alias").symlink_to(specs / "001-real", target_is_directory=True)

    found = detect.find_speckit_spec_files(specs)

    assert len(found) == 1, [str(p) for p in found]


def test_profile_does_not_double_count_feature_dirs(tmp_path: Path) -> None:
    repo = tmp_path
    _machinery(repo)
    write_speckit_spec(repo, "001-real", (FX / "good_speckit.md").read_text(encoding="utf-8"))
    specs = repo / "specs"
    (specs / "002-alias").symlink_to(specs / "001-real", target_is_directory=True)

    profile = detect.profile(repo)

    assert len(profile.feature_dirs) == 1, [str(d) for d in profile.feature_dirs]


# --- The graph, where the duplication was visible ---


def test_the_graph_renders_one_node_per_real_requirement(tmp_path: Path) -> None:
    """The symptom that made this worth fixing: a duplicated spec produced
    duplicate requirement nodes, so the graph showed work that does not
    exist."""
    repo = tmp_path
    _machinery(repo)
    write_speckit_spec(repo, "001-real", (FX / "good_speckit.md").read_text(encoding="utf-8"))
    specs = repo / "specs"
    (specs / "002-alias").symlink_to(specs / "001-real", target_is_directory=True)

    graph = json.loads(run_cli(repo, "graph", "--format", "json").stdout)
    spec_nodes = [n for n in graph["nodes"] if n.get("type") == "spec"]

    assert len(spec_nodes) == 1, spec_nodes


def test_the_real_package_keeps_its_own_name_under_change(tmp_path: Path) -> None:
    """The observable consequence of dedup, and the reason the tie-break is
    not merely cosmetic: `--change` addresses the surviving name. It must be
    the real package's, even when the alias sorts first."""
    repo = tmp_path
    _machinery(repo)
    write_spec(repo, "real-change", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    changes = repo / "openspec" / "changes"
    (changes / "alias-change").symlink_to(changes / "real-change", target_is_directory=True)

    assert run_cli(repo, "validate", "--change", "real-change").returncode == 0


def test_an_alias_name_reports_no_specs_found(tmp_path: Path) -> None:
    """The other half, stated so it is a decision rather than a surprise: two
    directories that are one package resolve to one, so the alias name no
    longer addresses anything and exits 2 rather than silently re-linting the
    same spec under a second name."""
    repo = tmp_path
    _machinery(repo)
    write_spec(repo, "real-change", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    changes = repo / "openspec" / "changes"
    (changes / "alias-change").symlink_to(changes / "real-change", target_is_directory=True)

    result = run_cli(repo, "validate", "--change", "alias-change")

    assert result.returncode == 2
    assert "no specs found for change 'alias-change'" in result.stderr


def test_two_real_features_are_still_two_nodes(tmp_path: Path) -> None:
    """Non-success criterion: dedup must not collapse distinct features. If
    this ever fails, the fix has started hiding real specs."""
    repo = tmp_path
    _machinery(repo)
    body = (FX / "good_speckit.md").read_text(encoding="utf-8")
    write_speckit_spec(repo, "001-one", body)
    write_speckit_spec(repo, "002-two", body)

    found = detect.find_speckit_spec_files(repo / "specs")

    assert len(found) == 2, [str(p) for p in found]
