"""SARIF 2.1.0 output, the composite action, and the pre-commit hooks file.

`AC-SA-1..16`. The format's value is placement: the same findings `validate`
already prints, delivered onto the diff in the pull request a team already
reviews rather than into a CI log nobody opens. So the properties worth
guarding are the ones that decide whether an annotation lands on the right
line of the right file — and the ones that decide whether a finding survives
the trip at all.

Two of those are less obvious than they look:

- **Every** finding currently has `line == 0`, because no rule sets a line.
  Clamping that to SARIF's minimum of 1 would put a wrong annotation on the
  first line of every file in every pull request, and a reviewer could not
  tell it was wrong. The region is omitted instead.
- A finding with no path must still be emitted. Dropping it would lose a real
  result to make a schema happy, which is the one failure this format must
  not introduce.
"""

from __future__ import annotations

import json
from pathlib import Path

from openspec_graph import sarif
from openspec_graph.rule_types import ERROR, INFO, WARN, Finding
from openspec_graph.rules import rule_table
from tests.support import run_cli, write_spec

REPO_ROOT = Path(__file__).resolve().parent.parent
FX = Path(__file__).resolve().parent / "fixtures"

# A spec body that trips rules, so the SARIF under test carries real results
# rather than passing vacuously on an empty list.
FINDING_BEARING = "# Nothing normative here\n\nProse only.\n"


def _repo(root: Path, *, with_findings: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "pyproject.toml").write_text(
        (FX / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_spec(root, "c1", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    if with_findings:
        write_spec(root, "zeta", "cap", FINDING_BEARING)
        write_spec(root, "alpha", "cap", FINDING_BEARING)
    return root


def _sarif(repo: Path) -> dict:
    result = run_cli(repo, "validate", "--format", "sarif")
    assert result.returncode in (0, 1), result.stderr
    return json.loads(result.stdout)


def _results(repo: Path) -> list[dict]:
    return _sarif(repo)["runs"][0]["results"]


# --- Shape ---


def test_sarif_output_has_the_required_2_1_0_shape(tmp_path: Path) -> None:
    """AC-SA-1: asserted structurally rather than against a fetched schema —
    the suite has no network, and a test that silently skips offline would be
    a gate that is not one."""
    log = _sarif(_repo(tmp_path))

    assert log["version"] == sarif.SARIF_VERSION
    assert log["$schema"] == sarif.SARIF_SCHEMA_URI
    assert len(log["runs"]) == 1
    driver = log["runs"][0]["tool"]["driver"]
    assert driver["name"] == "planlint"
    assert driver["rules"]
    assert isinstance(log["runs"][0]["results"], list)


def test_sarif_and_json_report_the_same_finding_multiset(tmp_path: Path) -> None:
    """AC-SA-2: the no-divergence claim, checked rather than asserted. Both
    renderings come from one traversal, so this pins that they still do."""
    repo = _repo(tmp_path)

    sarif_keys = sorted(
        (
            r["ruleId"],
            (r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] if r["locations"] else None),
        )
        for r in _results(repo)
    )
    payload = json.loads(run_cli(repo, "validate", "--json").stdout)
    json_keys = sorted((f["rule"], f["path"]) for f in payload["findings"])

    assert sarif_keys, "fixture produced no findings; the comparison would be vacuous"
    assert sarif_keys == json_keys


def test_sarif_results_are_ordered_like_the_text_renderer(tmp_path: Path) -> None:
    """AC-SA-11: all three renderings of one run agree on order."""
    repo = _repo(tmp_path)

    sarif_order = [
        (
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] if r["locations"] else "None",
            r["ruleId"],
        )
        for r in _results(repo)
    ]
    payload = json.loads(run_cli(repo, "validate", "--json").stdout)
    json_order = [(f["path"], f["rule"]) for f in payload["findings"]]

    assert sarif_order == json_order
    assert sarif_order == sorted(sarif_order)


def test_sarif_output_is_byte_stable_across_runs(tmp_path: Path) -> None:
    """AC-SA-12: a report that shuffles between runs cannot be diffed."""
    repo = _repo(tmp_path)

    first = run_cli(repo, "validate", "--format", "sarif").stdout
    second = run_cli(repo, "validate", "--format", "sarif").stdout

    assert first == second


# --- Severity ---


def test_error_severity_maps_to_sarif_error() -> None:
    """AC-SA-3: an ERROR must never arrive as anything softer."""
    assert sarif._level(ERROR) == "error"


def test_severity_map_covers_every_severity() -> None:
    """AC-SA-3: the map is total over the vocabulary the CLI uses, so no
    severity falls through to the fallback by accident."""
    from openspec_graph.cli import SEVERITY_ORDER

    assert {sarif._level(s) for s in SEVERITY_ORDER} == {"error", "warning", "note"}
    assert sarif._level(WARN) == "warning"
    assert sarif._level(INFO) == "note"


def test_an_unknown_severity_maps_up_not_to_none(tmp_path: Path) -> None:
    """AC-SA-3 (non-success): a severity this module has not been taught is a
    caller bug, and the safe failure is the loud one. Mapping it to "none"
    would hide a finding in the one surface an adopter actually reads."""
    assert sarif._level("CATASTROPHE") == "error"


# --- Locations ---


def test_a_finding_with_no_path_is_emitted_without_a_location(tmp_path: Path) -> None:
    """AC-SA-4 (non-success): losing a finding to satisfy a schema is the
    failure this format must not introduce. An empty locations array is valid
    SARIF and honest; a synthetic uri would assert a file."""
    log = sarif.to_sarif(
        [Finding("G006", ERROR, "orphan invariant", path=None)],
        rule_table(),
        root=tmp_path,
    )

    result = log["runs"][0]["results"][0]
    assert result["locations"] == []
    assert result["ruleId"] == "G006"


def test_no_finding_is_ever_dropped_from_the_sarif_log(tmp_path: Path) -> None:
    """AC-SA-4 (non-success): every finding in, every finding out — including
    the pathless one that has nowhere to be annotated."""
    findings = [
        Finding("G001", ERROR, "a", path=tmp_path / "one.md"),
        Finding("G006", WARN, "b", path=None),
        Finding("G002", INFO, "c", path=tmp_path / "two.md", line=12),
    ]

    log = sarif.to_sarif(findings, rule_table(), root=tmp_path)

    assert len(log["runs"][0]["results"]) == len(findings)


def test_a_line_of_zero_emits_no_region(tmp_path: Path) -> None:
    """AC-SA-5 (non-success): the case that matters most, because it is every
    finding. SARIF's startLine minimum is 1, so a 0 cannot be represented —
    and inventing line 1 would annotate content the finding is not about."""
    log = sarif.to_sarif(
        [Finding("G001", ERROR, "msg", path=tmp_path / "spec.md", line=0)],
        rule_table(),
        root=tmp_path,
    )

    physical = log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert "region" not in physical, physical


def test_a_real_line_emits_a_start_line(tmp_path: Path) -> None:
    """AC-SA-5: and a finding that does carry a line still points at it."""
    log = sarif.to_sarif(
        [Finding("G001", ERROR, "msg", path=tmp_path / "spec.md", line=42)],
        rule_table(),
        root=tmp_path,
    )

    physical = log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert physical["region"]["startLine"] == 42


def test_artifact_uri_is_repository_relative_posix(tmp_path: Path) -> None:
    """AC-SA-6: an absolute runner path resolves to nothing on the machine
    reading the annotation."""
    repo = _repo(tmp_path)

    for result in _results(repo):
        if not result["locations"]:
            continue
        uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        assert not Path(uri).is_absolute(), uri
        assert "\\" not in uri
        assert str(repo) not in uri


def test_artifact_location_carries_the_srcroot_base_id(tmp_path: Path) -> None:
    """AC-SA-6: the base id is what makes the relative uri resolvable."""
    repo = _repo(tmp_path)

    located = [r for r in _results(repo) if r["locations"]]
    assert located, "no located results; the assertion would be vacuous"
    for result in located:
        assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uriBaseId"] == (
            sarif.SRCROOT
        )


# --- The driver's rule set ---


def test_driver_rules_mirror_the_rule_table(tmp_path: Path) -> None:
    """AC-SA-7: the whole registry, not only the rules that fired. GitHub
    attaches alert metadata by ruleId against this set, so a rule firing for
    the first time in a later run would otherwise arrive unnamed."""
    log = _sarif(_repo(tmp_path))

    driver_ids = [r["id"] for r in log["runs"][0]["tool"]["driver"]["rules"]]
    assert driver_ids == [r["id"] for r in rule_table()]


def test_every_result_rule_index_resolves_to_its_rule_id(tmp_path: Path) -> None:
    """AC-SA-8: a ruleIndex pointing at the wrong rule is worse than none."""
    log = _sarif(_repo(tmp_path))
    rules = log["runs"][0]["tool"]["driver"]["rules"]

    for result in log["runs"][0]["results"]:
        if "ruleIndex" in result:
            assert rules[result["ruleIndex"]]["id"] == result["ruleId"]


def test_driver_rule_dialects_are_a_list_not_exploded_characters() -> None:
    """The rule table renders dialects as a comma-joined string, so a naive
    list() would turn "harness,upstream" into single characters — a bug that
    reads as working because the common value, "*", is one character long."""
    log = sarif.to_sarif([], rule_table())

    by_id = {r["id"]: r for r in log["runs"][0]["tool"]["driver"]["rules"]}
    assert by_id["G001"]["properties"]["dialects"] == ["*"]
    multi = [r for r in by_id.values() if len(r["properties"]["dialects"]) > 1]
    assert multi, "no multi-dialect rule in the registry; the check is vacuous"
    for rule in multi:
        assert all(len(d) > 1 for d in rule["properties"]["dialects"]), rule


# --- Flag interactions ---


def test_json_flag_is_an_exact_alias_of_format_json(tmp_path: Path) -> None:
    """AC-SA-9: `--json` predates `--format` and must keep working, byte for
    byte, or every existing caller and CI template breaks."""
    repo = _repo(tmp_path)

    assert (
        run_cli(repo, "validate", "--json").stdout
        == run_cli(repo, "validate", "--format", "json").stdout
    )


def test_json_with_format_json_is_accepted(tmp_path: Path) -> None:
    """AC-SA-9: they agree, so passing both is redundant, not a conflict."""
    repo = _repo(tmp_path)

    result = run_cli(repo, "validate", "--json", "--format", "json")

    assert result.returncode in (0, 1)
    assert json.loads(result.stdout)["findings"]


def test_json_with_format_sarif_is_a_usage_error(tmp_path: Path) -> None:
    """AC-SA-10 (non-success): honouring either silently would hand a caller
    a format it did not ask for and cannot parse."""
    repo = _repo(tmp_path)

    result = run_cli(repo, "validate", "--json", "--format", "sarif")

    assert result.returncode == 2
    assert result.stdout.strip() == ""
    assert "--json" in result.stderr


def test_sarif_returns_the_same_exit_code_as_the_text_run(tmp_path: Path) -> None:
    """AC-SA-17 (R-SA-14): the format decides how findings are rendered, never
    whether the gate passes.

    A CI job that switched to SARIF to get annotations must not also, silently,
    stop failing — that would turn a gate into a decoration, which is the exact
    failure mode this project exists to catch elsewhere.
    """
    failing = _repo(tmp_path / "failing")
    clean = _repo(tmp_path / "clean", with_findings=False)

    for repo in (failing, clean):
        text = run_cli(repo, "validate", "--fail-on", "ERROR").returncode
        sarif_code = run_cli(repo, "validate", "--fail-on", "ERROR", "--format", "sarif").returncode
        json_code = run_cli(repo, "validate", "--fail-on", "ERROR", "--json").returncode
        assert text == sarif_code == json_code, (repo.name, text, sarif_code, json_code)

    # And the fixture actually exercises both outcomes, so the equality above
    # is not three zeroes agreeing with each other.
    assert run_cli(failing, "validate", "--fail-on", "ERROR").returncode == 1
    assert run_cli(clean, "validate", "--fail-on", "ERROR").returncode == 0


def test_graph_format_choices_are_unchanged(tmp_path: Path) -> None:
    """AC-SA-18 (C-SA-5): adding a format to `validate` must not leak into
    `graph`, whose own `--format` has a settled surface — and whose `dot`
    rejection is a recorded non-goal, not an omission waiting to be filled."""
    from openspec_graph.cli import build_parser

    parser = build_parser()
    graph_sub = next(
        action.choices["graph"]
        for action in parser._actions
        if hasattr(action, "choices") and isinstance(action.choices, dict) and "graph" in action.choices
    )
    fmt = next(a for a in graph_sub._actions if "--format" in a.option_strings)

    # `dot` is deliberately an accepted *choice* that is then refused at
    # runtime with a message naming the supported formats (AC-GV-4). That is
    # not an oversight: argparse's own rejection would say only "invalid
    # choice", where the point is to explain that image rendering is out of
    # scope rather than unimplemented.
    assert sorted(fmt.choices) == ["dot", "json", "mermaid"]

    repo = _repo(tmp_path)
    rejected = run_cli(repo, "graph", "--format", "dot")
    assert rejected.returncode == 2
    assert rejected.stdout.strip() == ""


# --- The adopter-facing files ---


def test_the_composite_action_declares_the_expected_steps() -> None:
    """AC-SA-14: text-level assertions, because nothing in this suite imports
    a YAML parser and adding a dependency for one guard is not worth it."""
    action = (REPO_ROOT / ".github" / "actions" / "planlint" / "action.yml").read_text(
        encoding="utf-8"
    )

    assert "using: composite" in action
    assert "planlint --target" in action
    assert "detect" in action
    assert "--format sarif" in action
    assert "upload-sarif" in action


def test_pre_commit_hooks_file_declares_a_validate_hook() -> None:
    """AC-SA-15: the adopter-facing hook definition."""
    hooks = (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")

    assert "id: planlint" in hooks
    assert "validate" in hooks


def test_the_two_pre_commit_files_do_not_collide() -> None:
    """AC-SA-15: `.pre-commit-hooks.yaml` is what adopters consume;
    `.pre-commit-config.yaml` is what contributors run here. They are
    different files with different audiences, and confusing them is the first
    question a reviewer asks."""
    hooks = REPO_ROOT / ".pre-commit-hooks.yaml"
    config = REPO_ROOT / ".pre-commit-config.yaml"

    assert hooks.exists() and config.exists()
    assert hooks.read_text(encoding="utf-8") != config.read_text(encoding="utf-8")

    # The contributor config invokes this repository's own make targets; the
    # adopter hooks file must not, because an adopter's repository has none.
    # Asserted against the `entry:` lines rather than the whole file: prose
    # may legitimately mention make targets, and matching that would be a
    # test failing on its own documentation.
    entries = [
        line.split("entry:", 1)[1].strip()
        for line in hooks.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("entry:")
    ]
    assert entries, "no hook entry points found"
    for entry in entries:
        assert entry.startswith("planlint "), entry
        assert "make" not in entry.split(), entry
