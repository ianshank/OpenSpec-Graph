"""`delta` reports staleness the machinery *caused* — `AC-DL-1..12`.

The property that makes this verb worth having, and the one every test here
circles: a citation must have been **supported at the baseline** and be
unsupported now. A citation that was already broken before the comparison
began belongs to `validate` (G004/G005/G008), not here. Without that
attribution, `delta` would be a second, worse `validate` — the same findings
under a different name, and a reader unable to tell which of them their own
change caused.

The headline case the roadmap names is the coverage floor: you moved it, and
these specs still cite the old number while passing every gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from openspec_graph import delta, detect
from openspec_graph.parse import parse_spec
from tests.support import run_cli, write_spec

FX = Path(__file__).resolve().parent / "fixtures"


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "pyproject.toml").write_text(
        (FX / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_spec(root, "c1", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    return root


def _baseline(repo: Path, tmp_path: Path, name: str = "baseline.json") -> Path:
    """A real dialect card, produced the way an adopter would produce one."""
    path = tmp_path / name
    result = run_cli(repo, "detect", "--format", "json")
    assert result.returncode == 0, result.stderr
    path.write_text(result.stdout, encoding="utf-8")
    return path


def _remove_make_target(repo: Path, target: str) -> None:
    makefile = repo / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    makefile.write_text(text.replace(f"\n{target}:", f"\nold{target}:"), encoding="utf-8")


def _move_floor(repo: Path, old: int, new: int) -> None:
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(text.replace(f"fail_under = {old}", f"fail_under = {new}"), encoding="utf-8")


# --- The attribution property ---


def test_delta_names_the_removed_make_target(tmp_path: Path) -> None:
    """AC-DL-1: the citation was executable at the baseline and is not now."""
    repo = _repo(tmp_path / "repo")
    baseline = _baseline(repo, tmp_path)
    _remove_make_target(repo, "regression")

    result = run_cli(repo, "delta", "--baseline", str(baseline))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "make regression" in result.stdout


def test_delta_ignores_a_citation_already_broken_in_the_baseline(tmp_path: Path) -> None:
    """AC-DL-2 (non-success): the criterion that separates this verb from
    `validate`. A spec citing a target that never existed is a real finding —
    G004 reports it — but nothing about it changed, so it is not a delta.

    If this ever fails, `delta` has become a slower `validate` with worse
    wording, and its output stops answering "what did my change break".
    """
    repo = _repo(tmp_path / "repo")
    body = (FX / "good_harness.md").read_text(encoding="utf-8").replace(
        "`make regression`", "`make neverexisted`"
    )
    write_spec(repo, "always-broken", "cap", body)
    baseline = _baseline(repo, tmp_path)

    delta_out = run_cli(repo, "delta", "--baseline", str(baseline)).stdout
    validate_out = run_cli(repo, "validate").stdout

    assert "neverexisted" not in delta_out, delta_out
    # And the finding is not lost — the other verb still reports it.
    assert "neverexisted" in validate_out


def test_delta_on_an_identical_baseline_is_empty(tmp_path: Path) -> None:
    """AC-DL-3 (non-success): delta manufactures nothing. Same repo, same
    card, exit 0 and an empty list."""
    repo = _repo(tmp_path / "repo")
    baseline = _baseline(repo, tmp_path)

    result = run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json")

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["stale"] == []


def test_delta_reports_a_spec_citing_the_old_coverage_floor(tmp_path: Path) -> None:
    """AC-DL-4: the headline case. A spec that hard-codes the floor keeps
    passing every gate while stating a number the repository has changed."""
    repo = _repo(tmp_path / "repo")
    body = (FX / "good_harness.md").read_text(encoding="utf-8").replace(
        "## Acceptance Criteria",
        "## Acceptance Criteria\n\n- [ ] **AC-X-9:** coverage stays at or above 90% "
        "for the package.\n  _Verified by:_ `pytest -k test_x` · stage: `make test`\n",
        1,
    )
    write_spec(repo, "cites-floor", "cap", body)
    baseline = _baseline(repo, tmp_path)
    _move_floor(repo, 90, 95)

    result = run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json")

    stale = json.loads(result.stdout)["stale"]
    thresholds = [e for e in stale if e["kind"] == "threshold"]
    assert thresholds, stale
    assert thresholds[0]["was"] == "90"
    assert thresholds[0]["now"] == "95"


def test_delta_ignores_a_floor_that_did_not_move(tmp_path: Path) -> None:
    """AC-DL-4 (non-success): citing the floor is only stale once the floor
    moves. A spec naming the current number is correct, not a finding."""
    repo = _repo(tmp_path / "repo")
    body = (FX / "good_harness.md").read_text(encoding="utf-8").replace(
        "## Acceptance Criteria",
        "## Acceptance Criteria\n\n- [ ] **AC-X-9:** coverage stays at or above 90% "
        "for the package.\n  _Verified by:_ `pytest -k test_x` · stage: `make test`\n",
        1,
    )
    write_spec(repo, "cites-floor", "cap", body)
    baseline = _baseline(repo, tmp_path)

    result = run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json")

    assert [e for e in json.loads(result.stdout)["stale"] if e["kind"] == "threshold"] == []


def test_delta_names_the_removed_invariant(tmp_path: Path) -> None:
    """AC-DL-3: an invariant that was declared at the baseline and has since
    been deleted from the contract."""
    repo = _repo(tmp_path / "repo")
    contract = repo / "CONTRACT.md"
    contract.write_text("# Contract\n\n- INV-1: the first invariant.\n", encoding="utf-8")
    baseline = _baseline(repo, tmp_path)
    contract.write_text("# Contract\n\n(no invariants declared)\n", encoding="utf-8")

    payload = json.loads(
        run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    )
    invariants = [e for e in payload["stale"] if e["kind"] == "invariant"]

    assert invariants, payload["stale"]
    assert invariants[0]["subject"] == "INV-1"


def test_delta_names_the_removed_adr(tmp_path: Path) -> None:
    """AC-DL-3: the same discipline for architecture decision records."""
    repo = _repo(tmp_path / "repo")
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-first.md").write_text("# ADR-1: the first decision\n", encoding="utf-8")
    body = (FX / "good_harness.md").read_text(encoding="utf-8").replace(
        "## Acceptance Criteria",
        "## Acceptance Criteria\n\nImplements ADR-1.\n",
        1,
    )
    write_spec(repo, "cites-adr", "cap", body)
    baseline = _baseline(repo, tmp_path)
    (adr_dir / "0001-first.md").unlink()

    payload = json.loads(
        run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    )
    adrs = [e for e in payload["stale"] if e["kind"] == "adr"]

    assert adrs, payload["stale"]
    assert adrs[0]["subject"] == "ADR-1"


def test_every_delta_entry_corresponds_to_a_machinery_change(tmp_path: Path) -> None:
    """AC-DL-4: the load-bearing property, checked mechanically rather than
    asserted in prose.

    Attribution is this verb's whole justification, so it must not be
    possible to report a stale citation while the machinery diff is empty.
    If the machinery did not move, nothing moved out from under a spec, and
    any entry produced would be a `validate` finding wearing a different hat.
    """
    repo = _repo(tmp_path / "repo")
    write_spec(repo, "c2", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    baseline = _baseline(repo, tmp_path)
    _remove_make_target(repo, "regression")

    payload = json.loads(
        run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    )

    assert payload["stale"], "fixture produced no entries; the check would be vacuous"
    assert payload["machinery_changes"], (
        "entries were reported while the machinery diff was empty — the "
        "attribution claim is broken"
    )


# --- The exit-code contract ---


def test_cli_delta_with_missing_baseline_is_a_usage_error(tmp_path: Path) -> None:
    """AC-DL-5: a missing baseline is a precondition failure, not a report."""
    repo = _repo(tmp_path / "repo")

    result = run_cli(repo, "delta", "--baseline", str(tmp_path / "absent.json"))

    assert result.returncode == 2
    assert "--baseline" in result.stderr


def test_cli_delta_with_a_non_object_baseline_is_a_usage_error(tmp_path: Path) -> None:
    """AC-DL-5: valid JSON that is not a card is still not a card."""
    repo = _repo(tmp_path / "repo")
    bad = tmp_path / "array.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")

    result = run_cli(repo, "delta", "--baseline", str(bad))

    assert result.returncode == 2
    assert "expected a JSON object" in result.stderr


def test_cli_delta_with_malformed_json_is_a_usage_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")

    result = run_cli(repo, "delta", "--baseline", str(bad))

    assert result.returncode == 2


def test_cli_delta_without_a_spec_tree_is_a_usage_error(tmp_path: Path) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "Makefile").write_text("test:\n\techo hi\n", encoding="utf-8")
    baseline = tmp_path / "card.json"
    baseline.write_text("{}", encoding="utf-8")

    result = run_cli(bare, "delta", "--baseline", str(baseline))

    assert result.returncode == 2
    assert "planlint init" in result.stderr


# --- Output shape ---


def test_cli_delta_json_lists_stale_citations_with_schema_version(tmp_path: Path) -> None:
    """AC-DL-6: same envelope discipline as every other machine-readable
    output, and byte-identical on re-run."""
    repo = _repo(tmp_path / "repo")
    baseline = _baseline(repo, tmp_path)
    _remove_make_target(repo, "regression")

    payload = json.loads(
        run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    )
    assert payload["schema_version"] == delta.DELTA_SCHEMA_VERSION
    assert payload["tool_version"]
    assert set(payload) == {
        "schema_version",
        "tool_version",
        "target",
        "baseline",
        "machinery_changes",
        "stale",
    }


def test_cli_delta_json_is_byte_identical_across_runs(tmp_path: Path) -> None:
    """AC-DL-7: the determinism every machine-readable output in this tool
    commits to. A report that shuffles between runs cannot be diffed, which
    is most of what a CI consumer wants it for."""
    repo = _repo(tmp_path / "repo")
    write_spec(repo, "c2", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    baseline = _baseline(repo, tmp_path)
    _remove_make_target(repo, "regression")

    first = run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    second = run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout

    assert first == second
    assert json.loads(first)["stale"], "fixture produced no entries; ordering is untested"


def test_delta_paths_are_repository_relative(tmp_path: Path) -> None:
    """AC-DL-7: the same portability rule the findings envelope follows — a
    delta report produced on a runner has to mean something elsewhere."""
    repo = _repo(tmp_path / "repo")
    baseline = _baseline(repo, tmp_path)
    _remove_make_target(repo, "regression")

    payload = json.loads(
        run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    )

    for entry in payload["stale"]:
        assert not Path(entry["path"]).is_absolute(), entry
        assert "\\" not in entry["path"]
        assert str(repo) not in entry["path"]


def test_cli_delta_exits_zero_on_an_identical_baseline(tmp_path: Path) -> None:
    """AC-DL-8: "the floor moved and no spec cited it" is a useful answer.
    Printing nothing would leave a reader unsure the baseline was read."""
    repo = _repo(tmp_path / "repo")
    baseline = _baseline(repo, tmp_path)
    _move_floor(repo, 90, 95)

    result = run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json")

    payload = json.loads(result.stdout)
    assert payload["machinery_changes"], "the floor moved and was not reported"
    assert payload["stale"] == []
    assert result.returncode == 0


def test_cli_delta_never_writes_to_the_target_repo(tmp_path: Path) -> None:
    """AC-DL-9 (non-success): `delta` is a read-only verb, like `detect`."""
    repo = _repo(tmp_path / "repo")
    baseline = _baseline(repo, tmp_path)
    before = {p: p.stat().st_mtime_ns for p in sorted(repo.rglob("*")) if p.is_file()}

    run_cli(repo, "delta", "--baseline", str(baseline))

    after = {p: p.stat().st_mtime_ns for p in sorted(repo.rglob("*")) if p.is_file()}
    assert before == after


# --- The pure module ---


def test_delta_skips_a_field_absent_from_an_older_baseline_card(tmp_path: Path) -> None:
    """AC-DL-10 (non-success): a card saved before a field existed never
    tracked that dimension. Reading its absence as "everything was removed"
    would report every tool upgrade as repository drift — the same
    schema-addition trap `diff_cards` documents.
    """
    repo = _repo(tmp_path / "repo")
    profile = detect.profile(repo)
    specs = [parse_spec(p, "harness") for p in detect.find_spec_files(repo / "openspec")]

    # A card from a hypothetical older tool: no make_targets key at all.
    entries = delta.build_delta({"schema_version": 1}, profile, specs, repo)

    assert entries == []


def test_delta_entries_are_stable_ordered(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    write_spec(repo, "aaa", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    write_spec(repo, "zzz", "cap", (FX / "good_harness.md").read_text(encoding="utf-8"))
    baseline = _baseline(repo, tmp_path)
    _remove_make_target(repo, "regression")

    payload = json.loads(
        run_cli(repo, "delta", "--baseline", str(baseline), "--format", "json").stdout
    )
    keys = [(e["path"], e["kind"], e["subject"]) for e in payload["stale"]]

    assert keys == sorted(keys)


def test_delta_entries_never_reach_the_finding_stream() -> None:
    """AC-DL-11 (non-success): a DeltaEntry must never be mistaken for a rule
    finding. If it grew a `rule`/`severity` shape it would start leaking into
    `rules --json`, `validate`'s counts and the graph's broken_links, none of
    which this verb participates in."""
    entry = delta.DeltaEntry(
        kind=delta.KIND_MAKE_TARGET,
        path="p",
        subject="s",
        was="present",
        now="removed",
        detail="d",
    )

    assert set(entry.as_dict()) == {"kind", "path", "subject", "was", "now", "detail"}
    assert "severity" not in entry.as_dict()


def test_delta_ignores_an_ambiguous_threshold_line() -> None:
    """AC-DL-12: `9` must not match inside `90`, and `90` must not match
    inside `190`. A substring test would report the wrong specs and, worse,
    would look like it worked on the common case."""
    assert delta._mentions_value("coverage at or above 90%", 90)
    assert delta._mentions_value(">= 90", 90)
    assert not delta._mentions_value("coverage at or above 90%", 9)
    assert not delta._mentions_value("a floor of 190", 90)
    assert not delta._mentions_value("no digits here", 90)
    # A run that ends the string still matches (no trailing separator).
    assert delta._mentions_value("floor is 90", 90)

    # Decimals are one number, not two. Both of these matched a floor of 90
    # before the matcher was fixed: a spec citing 90.5 is not citing 90, and a
    # version string is not a threshold at all. A false positive here would
    # land in the one report this verb exists to make trustworthy.
    assert not delta._mentions_value("coverage at or above 90.5%", 90)
    assert not delta._mentions_value("planlint v9.90 build", 90)
    assert delta._mentions_value("a floor of 0", 0)
