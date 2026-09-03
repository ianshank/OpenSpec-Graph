"""Threshold detection and optional-config reading, at the unit level (CP-TC).

The corpus under ``tests/corpus/targets/`` pins whole-repository shapes. These
tests pin the three helpers underneath -- ``as_threshold_number``,
``scoped_fail_under`` and ``read_text_or_none`` -- on the inputs an
adversarial review showed the corpus did not reach: ``float()``'s permissive
grammar, TOML constructs that look like keys or headers, and files that are
not regular files. Each case here was a real misbehaviour before it was a
test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from openspec_graph import delta, detect
from openspec_graph.parse import parse_spec
from openspec_graph.parse_semantics import threshold_values

TABLE = detect.COVERAGE_REPORT_TABLE


# --- as_threshold_number ----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("90", 90),
        ("90.0", 90),
        ("85.5", 85.5),
        (" 90 ", 90),
        (90, 90),
        (90.0, 90),
        (0, 0),
        (100, 100),
    ],
)
def test_as_threshold_number_accepts_plain_decimals_in_range(raw: object, expected: object) -> None:
    value = detect.as_threshold_number(raw)
    assert value == expected
    assert type(value) is type(expected), "integral values must stay int; fractions float"


@pytest.mark.parametrize(
    "raw",
    [
        True,
        False,
        None,
        [90],
        {"lines": 90},
        "abc",
        "",
        "nan",
        "inf",
        float("inf"),
        float("nan"),
        # float() would accept every one of these; a coverage floor is none of them.
        "1e2",
        "1_000",
        "-5",
        "٩٠",
        "\uff11\uff12",  # full-width digits
        "+90",
        "90.",
        ".5",
        # In range for float(), out of range for a percentage.
        -1,
        101,
        "150",
        10**30,
    ],
)
def test_as_threshold_number_rejects_what_is_not_a_percentage(raw: object) -> None:
    assert detect.as_threshold_number(raw) is None


def test_as_threshold_number_can_refuse_strings_for_the_json_policy_path() -> None:
    """``governance-policy.json`` always took numbers only; a quoted value is
    a misconfiguration there, not a floor."""
    assert detect.as_threshold_number("90", accept_str=False) is None
    assert detect.as_threshold_number(90, accept_str=False) == 90


# --- scoped_fail_under ------------------------------------------------------


def _scoped(text: str) -> int | float | None:
    return detect.scoped_fail_under(text, TABLE)


def test_scoped_fail_under_reads_only_its_table() -> None:
    assert _scoped("[tool.coverage.report]\nfail_under = 90\n") == 90
    assert _scoped("[tool.other]\nfail_under = 50\n") is None
    assert _scoped("fail_under = 50\n[tool.coverage.report]\nshow_missing = true\n") is None


def test_scoped_fail_under_ignores_lines_inside_multiline_strings() -> None:
    """``exclude_lines`` is a free-text list that lives in exactly this table."""
    text = '[tool.coverage.report]\nexclude_lines = """\nfail_under = 42\n"""\nfail_under = 90\n'
    assert _scoped(text) == 90
    # A header-looking line inside the string must not reset the table either.
    text = '[tool.coverage.report]\nexclude_lines = """\n[tool.other]\n"""\nfail_under = 90\n'
    assert _scoped(text) == 90
    # ...and with no real floor after the string, there is no floor.
    assert _scoped('[tool.coverage.report]\nexclude_lines = """\nfail_under = 42\n"""\n') is None
    # Single-quoted delimiters behave the same.
    text = "[tool.coverage.report]\nexclude_lines = '''\nfail_under = 42\n'''\nfail_under = 90\n"
    assert _scoped(text) == 90


def test_scoped_fail_under_ignores_lines_inside_multiline_arrays() -> None:
    text = (
        "[tool.coverage.report]\n"
        "exclude_also = [\n"
        '  "fail_under = 3",\n'
        '  "[not a table]",\n'
        "  [1, 2],\n"
        "]\n"
        "fail_under = 90\n"
    )
    assert _scoped(text) == 90


@pytest.mark.parametrize(
    "header",
    ["[tool.coverage.report]", "[ tool.coverage.report ]", '["tool"."coverage"."report"]',
     "[tool . coverage . report]", "[tool.coverage.report]  # trailing comment"],
)
def test_scoped_fail_under_normalises_equivalent_table_headers(header: str) -> None:
    assert _scoped(f"{header}\nfail_under = 90\n") == 90


def test_scoped_fail_under_does_not_treat_an_array_of_tables_as_the_table() -> None:
    assert _scoped("[[tool.coverage.report]]\nfail_under = 90\n") is None


def test_scoped_fail_under_rejects_a_quoted_string_floor() -> None:
    assert _scoped('[tool.coverage.report]\nfail_under = "90"\n') is None


def test_scoped_fail_under_is_bom_tolerant_as_a_pure_function() -> None:
    """Same principle as ``machinery.parse_makefile``: public API that takes
    text must not depend on the caller having decoded carefully."""
    assert _scoped("﻿[tool.coverage.report]\nfail_under = 90\n") == 90


def test_scoped_fail_under_first_match_wins_and_subtables_do_not_count() -> None:
    assert _scoped("[tool.coverage.report]\nfail_under = 90\nfail_under = 80\n") == 90
    assert _scoped("[tool.coverage.report.extra]\nfail_under = 90\n") is None


# --- _read_ini_fail_under ---------------------------------------------------


def test_read_ini_fail_under_reads_a_bom_prefixed_file(tmp_path: Path) -> None:
    path = tmp_path / ".coveragerc"
    path.write_bytes(b"\xef\xbb\xbf[report]\nfail_under = 75\n")
    assert detect._read_ini_fail_under(path, "report") == 75


@pytest.mark.parametrize(
    "body",
    [
        "fail_under = 90\n",  # no section header -> configparser.Error
        "[report]\nfail_under = 80\nfail_under = 90\n",  # duplicate option
        "[report]\nshow_missing = true\n",  # key absent
        "[report]\nfail_under = abc\n",  # not a number
        "[report]\nfail_under = 1e2\n",  # float() grammar, not a percentage
    ],
)
def test_read_ini_fail_under_returns_none_rather_than_guessing(tmp_path: Path, body: str) -> None:
    path = tmp_path / ".coveragerc"
    path.write_text(body, encoding="utf-8")
    assert detect._read_ini_fail_under(path, "report") is None


def test_read_ini_fail_under_keeps_a_fractional_floor(tmp_path: Path) -> None:
    path = tmp_path / ".coveragerc"
    path.write_text("[report]\nfail_under = 85.5\n", encoding="utf-8")
    assert detect._read_ini_fail_under(path, "report") == 85.5


# --- governance-policy.json path -------------------------------------------


@pytest.mark.parametrize(
    "policy",
    [
        '{"coverage": []}',
        '{"coverage": {"lines": "abc"}}',
        '{"coverage": {"lines": "90"}}',  # numbers only on this locator
        '{"coverage": {"lines": -5}}',
        '{"coverage": {"lines": true}}',
        "[1, 2]",
        "not json",
    ],
)
def test_governance_policy_without_a_numeric_floor_falls_through(tmp_path: Path, policy: str) -> None:
    (tmp_path / "governance-policy.json").write_text(policy, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.coverage.report]\nfail_under = 90\n")
    profile = detect.profile(tmp_path)
    assert profile.threshold is not None
    assert profile.threshold.locator == f"pyproject.toml:[{TABLE}].fail_under"
    assert profile.threshold.value == 90


def test_governance_policy_accepts_a_bom_and_a_fractional_floor(tmp_path: Path) -> None:
    (tmp_path / "governance-policy.json").write_bytes(
        b'\xef\xbb\xbf{"coverage": {"lines": 85.5}}'
    )
    profile = detect.profile(tmp_path)
    assert profile.threshold is not None
    assert profile.threshold.value == 85.5


# --- read_text_or_none: not a regular file ---------------------------------


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are a POSIX feature")
def test_a_fifo_where_a_config_file_belongs_does_not_hang(tmp_path: Path) -> None:
    """``exists()`` is true for a FIFO and ``open()`` on one blocks until a
    writer appears -- forever, here. ``is_file()`` first, so ``detect`` never
    opens it. A clone cannot contain one, but a working tree can."""
    os.mkfifo(tmp_path / "Makefile")
    os.mkfifo(tmp_path / "pyproject.toml")
    profile = detect.profile(tmp_path)  # would block here before the fix
    assert profile.make_targets == ()
    assert profile.threshold is None


# --- the float floor reaches every consumer correctly ---------------------


def test_threshold_values_keeps_a_fraction_so_g003_compares_like_with_like() -> None:
    assert threshold_values("coverage >= 85.5%") == (85.5,)
    assert threshold_values("coverage >= 90%") == (90,)
    assert threshold_values("from 80% to 90%") == (80, 90)


def test_g003_does_not_flag_a_criterion_that_cites_the_exact_fractional_floor(
    tmp_path: Path,
) -> None:
    """Before ``threshold_values`` learned fractions, a repo whose floor was
    85.5 got a G003 on every criterion that cited it correctly."""
    from openspec_graph import rules

    (tmp_path / "Makefile").write_text("test:\n\t@echo t\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.coverage.report]\nfail_under = 85.5\n")
    spec = tmp_path / "openspec" / "changes" / "c1" / "specs" / "cap" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# Spec\n\n## Requirements\n\n- R-XY-1: Coverage holds.\n\n"
        "## Acceptance Criteria\n\n"
        "- [ ] **AC-XY-1:** Line coverage is >= 85.5% as pyproject.toml gates it. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_x` · stage: `make test`\n"
        "- [ ] **AC-XY-2 (non-success):** A drop below the floor fails `make test`. (R-XY-1)\n"
        "  _Verified by:_ `pytest -k test_y` · stage: `make test`\n",
        encoding="utf-8",
    )
    profile = detect.profile(tmp_path)
    findings = rules.evaluate(parse_spec(spec, "harness"), profile)
    assert not [f for f in findings if f.rule == "G003"], [f.message for f in findings]


def test_delta_reads_a_fractional_baseline_floor_and_ignores_booleans() -> None:
    assert delta._baseline_threshold({"threshold": {"value": 85.5}}) == 85.5
    assert delta._baseline_threshold({"threshold": {"value": 90}}) == 90
    assert delta._baseline_threshold({"threshold": {"value": True}}) is None
    assert delta._baseline_threshold({"threshold": None}) is None


# --- BOM tolerance reaches spec parsing too --------------------------------


def test_a_bom_prefixed_spec_keeps_its_first_line_criterion(tmp_path: Path) -> None:
    """``detect_dialect`` and ``parse_spec`` must see the same first line.

    The section grammar is ``^##`` anchored: a BOM ahead of a first-line
    ``## Acceptance Criteria`` heading made the section invisible, so every
    criterion under it vanished and the spec drew a G001 -- while dialect
    detection, already BOM-tolerant, happily classified the same file.
    """
    spec = tmp_path / "spec.md"
    spec.write_bytes(
        b"\xef\xbb\xbf## Acceptance Criteria\n\n"
        b"- [ ] **AC-XY-1:** First. (R-XY-1)\n"
        b"- [ ] **AC-XY-2 (non-success):** Second. (R-XY-1)\n"
    )
    parsed = parse_spec(spec, "harness")
    assert [c.ident for c in parsed.criteria] == ["AC-XY-1", "AC-XY-2"]


# --- byte specimens survive checkout ----------------------------------------


CORPUS = Path(__file__).resolve().parent / "corpus" / "targets"


@pytest.mark.parametrize(
    ("shape", "needle"),
    [
        ("bom-rule-first", b"\xef\xbb\xbf"),
        ("bom-phony-first", b"\xef\xbb\xbf"),
        ("crlf-makefile", b"\r\n"),
    ],
)
def test_byte_specimens_survived_checkout(shape: str, needle: bytes) -> None:
    """``.gitattributes`` marks the corpus ``-text``. If that ever regresses,
    a Windows checkout rewrites these bytes and the shapes silently test
    nothing; fail loudly instead."""
    assert needle in (CORPUS / shape / "repo" / "Makefile").read_bytes()


def test_detection_is_byte_stable_across_hash_seeds() -> None:
    """Card bytes must not depend on the interpreter's hash seed.

    Comparing two in-process calls cannot see set-iteration instability --
    the seed is fixed for the life of the process -- so the second card comes
    from a subprocess started with a different ``PYTHONHASHSEED``.
    """
    script = (
        "import json, sys; from pathlib import Path; from openspec_graph import detect; "
        "print(json.dumps({p.name: detect.profile(p / 'repo').to_card() "
        "for p in sorted(Path(sys.argv[1]).iterdir()) if (p / 'expected.json').is_file()}, "
        "sort_keys=True))"
    )
    outputs = []
    for seed in ("1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", script, str(CORPUS)],
            capture_output=True, text=True, check=True, env=env,
            cwd=Path(__file__).resolve().parent.parent,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0]), "the subprocess produced no cards"
