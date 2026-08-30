"""Tests for machinery.py -- the structural Makefile parser (CP-3).

One fixture per behavior, matching this project's existing per-rule-fixture
testing style. The non-execution test (AC-MP-2) is the most important test
in this file -- it is the only thing standing between this module and a
real safety regression, so treat it as load-bearing, not boilerplate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from openspec_graph import machinery


def test_multi_target_line_resolves_both_names() -> None:
    text = "lint typecheck: build\n\techo checking\nbuild:\n\techo building\n"
    facts = machinery.parse_makefile(text)
    assert {"lint", "typecheck", "build"} <= set(facts.targets)


def test_shell_expansion_in_target_position_never_executes(
    tmp_path: Path, monkeypatch
) -> None:
    """AC-MP-2. Proven two ways: subprocess.run/Popen raise if called at all,
    AND the marker file the payload would create never appears on disk."""
    marker = tmp_path / "pwned.marker"

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("machinery.parse_makefile must never invoke a subprocess")

    monkeypatch.setattr(subprocess, "run", _raise)
    monkeypatch.setattr(subprocess, "Popen", _raise)

    text = f"$(shell touch {marker}): build\n\techo hi\nbuild:\n\techo building\n"
    facts = machinery.parse_makefile(text)  # must not raise

    assert not marker.exists()
    assert "build" in facts.targets
    assert facts.unresolved_count >= 1
    assert facts.confidence == "low"


def test_phony_and_special_targets_are_excluded() -> None:
    text = (
        ".PHONY: build\n"
        ".SECONDARY:\n"
        ".DELETE_ON_ERROR:\n"
        "build:\n"
        "\techo hi\n"
    )
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("build",)


def test_pattern_rules_are_excluded_by_design() -> None:
    # DEC-MP-004: matches today's incidental behavior deliberately.
    text = "%.o: %.c\n\tgcc -c $< -o $@\nbuild: main.o\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert "%.o" not in facts.targets
    assert "build" in facts.targets


def test_variable_expansion_in_target_position_is_unresolved_not_guessed() -> None:
    text = "$(BINARY): $(SRCS)\n\techo building\nbuild:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert "build" in facts.targets
    assert facts.unresolved_count == 1
    assert facts.confidence == "low"


def test_conditional_block_unions_both_branches() -> None:
    text = (
        "ifeq ($(OS),Windows)\n"
        "win-build:\n"
        "\techo windows\n"
        "else\n"
        "unix-build:\n"
        "\techo unix\n"
        "endif\n"
    )
    facts = machinery.parse_makefile(text)
    assert {"win-build", "unix-build"} <= set(facts.targets)
    assert facts.has_conditional is True
    assert facts.confidence == "low"


def test_include_directive_lowers_confidence() -> None:
    text = "include extra.mk\nbuild:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert facts.has_include is True
    assert facts.confidence == "low"
    assert "build" in facts.targets


def test_target_specific_variable_assignment_still_resolves_the_target() -> None:
    text = "build: CFLAGS = -O2\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert "build" in facts.targets
    assert "CFLAGS" not in facts.targets


def test_double_colon_rule_resolves_the_target_name() -> None:
    text = "build:: main.c\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert "build" in facts.targets


def test_variable_assignment_line_is_not_a_target() -> None:
    text = "VAR := value\nOTHER = another\nbuild:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("build",)


def test_a_clean_makefile_parses_at_high_confidence() -> None:
    text = ".PHONY: build test\nbuild:\n\techo hi\ntest: build\n\techo test\n"
    facts = machinery.parse_makefile(text)
    assert facts.confidence == "high"
    assert facts.unresolved_count == 0
    assert facts.has_include is False
    assert facts.has_conditional is False


def test_blank_lines_and_top_level_comments_are_skipped() -> None:
    text = "\n# top-level comment\n\nbuild:\n\techo hi\n\n# trailing comment\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("build",)


def test_makefile_facts_targets_is_a_sorted_deduplicated_tuple() -> None:
    text = "b: a\n\techo b\na:\n\techo a\na:\n\techo a again\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("a", "b")
