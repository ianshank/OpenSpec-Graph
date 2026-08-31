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


def test_diff_cards_detects_an_adr_source_change() -> None:
    old = {"schema_version": 1, "adr_source": None, "adr_ids": []}
    new = {"schema_version": 1, "adr_source": "docs/adr", "adr_ids": ["ADR-1"]}
    changes = dialect_card.diff_cards(old, new)
    assert any("adr_source" in c for c in changes)
    assert any("adr_ids" in c for c in changes)


def test_diff_cards_does_not_report_a_field_absent_from_the_old_card_as_drift() -> None:
    # A pre-upgrade card saved before adr_ids existed has no such key at
    # all -- not `None`, absent. Comparing that absence against the new
    # card's default ([]) would report every schema-growing tool upgrade
    # as false repository drift on an unchanged repo (Copilot review
    # finding on PR #13; a latent bug present since this schema's first
    # additive field, not new to CP-AD).
    old = {"schema_version": 1, "dialect": "harness"}  # no adr_source/adr_ids key at all
    new = {"schema_version": 1, "dialect": "harness", "adr_source": None, "adr_ids": []}
    assert dialect_card.diff_cards(old, new) == []
