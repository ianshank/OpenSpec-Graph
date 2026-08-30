"""Tests for dialect_card.py -- the dialect-card schema and diff engine (CP-2).

Pure unit tests: diff_cards operates on plain dicts, no CLI/subprocess needed.
"""

from __future__ import annotations

from openspec_graph import dialect_card


def test_diff_cards_is_empty_when_nothing_changed() -> None:
    card = {
        "schema_version": 1,
        "dialect": "harness",
        "languages": ["python"],
        "make_targets": ["test"],
    }
    assert dialect_card.diff_cards(card, dict(card)) == []


def test_diff_cards_reports_a_changed_field() -> None:
    old = {"schema_version": 1, "dialect": "harness"}
    new = {"schema_version": 1, "dialect": "upstream"}
    changes = dialect_card.diff_cards(old, new)
    assert any("dialect" in c for c in changes)
    assert not any("schema_version" in c for c in changes)


def test_diff_cards_reports_schema_version_changes_distinctly() -> None:
    changes = dialect_card.diff_cards({"schema_version": 1}, {"schema_version": 2})
    assert len(changes) == 1
    assert "schema_version" in changes[0]


def test_diff_cards_reports_every_changed_field_independently() -> None:
    old = {"schema_version": 1, "dialect": "harness", "make_targets": ["test"]}
    new = {"schema_version": 1, "dialect": "upstream", "make_targets": ["test", "lint"]}
    changes = dialect_card.diff_cards(old, new)
    assert len(changes) == 2
    assert any("dialect" in c for c in changes)
    assert any("make_targets" in c for c in changes)
