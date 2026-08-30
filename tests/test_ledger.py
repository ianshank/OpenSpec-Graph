"""Tests for ledger.py -- the waiver ledger aggregator (CP-4).

Pure unit tests: build_ledger operates on ParsedSpec objects directly, no
CLI/subprocess needed (mirrors test_dialect_card.py's style).
"""

from __future__ import annotations

from pathlib import Path

from openspec_graph import ledger
from openspec_graph.parse import ParsedSpec, Waiver


def _spec(path: str, waivers: tuple[Waiver, ...] = ()) -> ParsedSpec:
    return ParsedSpec(
        path=Path(path),
        dialect="harness",
        sections=(),
        status=None,
        requirements=(),
        criteria=(),
        make_refs=(),
        invariant_refs=(),
        hard_coded_thresholds=(),
        delta_headers=(),
        waivers=waivers,
    )


def test_build_ledger_is_empty_with_no_waivers() -> None:
    assert ledger.build_ledger([_spec("openspec/changes/c1/specs/cap1/spec.md")]) == []


def test_build_ledger_captures_rule_path_line_reason() -> None:
    spec = _spec(
        "openspec/changes/c1/specs/cap1/spec.md",
        waivers=(Waiver(rule="G003", reason="policy exception", line=12),),
    )
    entries = ledger.build_ledger([spec])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.rule == "G003"
    assert entry.line == 12
    assert entry.reason == "policy exception"
    assert entry.path == "openspec/changes/c1/specs/cap1/spec.md"


def test_build_ledger_derives_owning_change() -> None:
    spec = _spec(
        "openspec/changes/add-waiver-ledger-and-inv-lints/specs/waiver-ledger/spec.md",
        waivers=(Waiver(rule="G003", reason="r", line=1),),
    )
    entries = ledger.build_ledger([spec])
    assert entries[0].change == "add-waiver-ledger-and-inv-lints"


def test_owning_change_is_none_outside_a_change_package() -> None:
    assert ledger.owning_change("README.md") is None
    assert ledger.owning_change("docs/next-steps.md") is None


def test_build_ledger_expands_a_multi_rule_comment_into_one_row_per_rule() -> None:
    # <!-- specgraph:allow G003,G004 shared reason --> parses to two Waiver
    # records sharing one line/reason; the ledger keeps them as two rows.
    spec = _spec(
        "openspec/changes/c1/specs/cap1/spec.md",
        waivers=(
            Waiver(rule="G003", reason="shared reason", line=5),
            Waiver(rule="G004", reason="shared reason", line=5),
        ),
    )
    entries = ledger.build_ledger([spec])
    assert {e.rule for e in entries} == {"G003", "G004"}
    assert all(e.line == 5 and e.reason == "shared reason" for e in entries)


def test_build_ledger_records_an_empty_reason_verbatim() -> None:
    spec = _spec(
        "openspec/changes/c1/specs/cap1/spec.md",
        waivers=(Waiver(rule="G003", reason="", line=1),),
    )
    entries = ledger.build_ledger([spec])
    assert entries[0].reason == ""


def test_build_ledger_orders_by_path_then_line_then_rule() -> None:
    specs = [
        _spec("openspec/changes/c2/specs/cap/spec.md", waivers=(Waiver(rule="G004", reason="r", line=1),)),
        _spec(
            "openspec/changes/c1/specs/cap/spec.md",
            waivers=(
                Waiver(rule="G004", reason="r", line=9),
                Waiver(rule="G003", reason="r", line=3),
            ),
        ),
    ]
    entries = ledger.build_ledger(specs)
    assert [(e.path, e.line, e.rule) for e in entries] == [
        ("openspec/changes/c1/specs/cap/spec.md", 3, "G003"),
        ("openspec/changes/c1/specs/cap/spec.md", 9, "G004"),
        ("openspec/changes/c2/specs/cap/spec.md", 1, "G004"),
    ]


def test_build_ledger_relativizes_path_against_root() -> None:
    spec = _spec(
        "/repo/openspec/changes/c1/specs/cap1/spec.md",
        waivers=(Waiver(rule="G003", reason="r", line=1),),
    )
    entries = ledger.build_ledger([spec], root=Path("/repo"))
    assert entries[0].path == "openspec/changes/c1/specs/cap1/spec.md"


def test_build_ledger_falls_back_to_the_full_path_when_not_under_root() -> None:
    # Mirrors graph._relative_to's own defensive fallback: a path that isn't
    # actually under the given root is reported as-is, not raised on.
    spec = _spec(
        "/elsewhere/openspec/changes/c1/specs/cap1/spec.md",
        waivers=(Waiver(rule="G003", reason="r", line=1),),
    )
    entries = ledger.build_ledger([spec], root=Path("/repo"))
    assert entries[0].path == "/elsewhere/openspec/changes/c1/specs/cap1/spec.md"


def test_ledger_entry_as_dict_shape() -> None:
    entry = ledger.LedgerEntry(rule="G003", path="p", line=1, reason="r", change="c1")
    assert entry.as_dict() == {"rule": "G003", "path": "p", "line": 1, "reason": "r", "change": "c1"}
