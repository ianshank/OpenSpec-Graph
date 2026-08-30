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


def test_define_block_body_is_never_parsed_as_a_rule() -> None:
    # A define...endef body is commonly written at column 0 with no leading
    # tab, so "Usage: make test" is a realistic body line -- without the
    # in_define skip, it would match _RULE_LINE and fabricate "Usage" as a
    # target that does not exist.
    text = "define HELP_TEXT\nUsage: make test\nendef\nbuild:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert "Usage" not in facts.targets
    assert facts.targets == ("build",)
    assert facts.has_define is True
    assert facts.confidence == "low"


def test_define_block_suppresses_directive_and_conditional_detection_inside_it() -> None:
    # A line that looks like an include/conditional directive inside a
    # define block is opaque replacement text too, not a real directive.
    text = "define HELP_TEXT\ninclude other.mk\nifeq (a,b)\nendef\nbuild:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert facts.has_include is False
    assert facts.has_conditional is False
    assert facts.has_define is True
    assert facts.targets == ("build",)


def test_nested_define_blocks_resolve_at_the_outer_endef_not_the_inner_one() -> None:
    # Verified against real GNU Make: a `define` appearing inside another
    # `define`'s body opens a second, inner block -- the whole nested
    # structure only closes at the matching *outer* endef. A boolean
    # in_define flag (rather than a depth counter) would incorrectly
    # treat the first endef as closing everything, leaving "inner-body:"
    # to be parsed as a real (fabricated) target.
    text = (
        "define OUTER\n"
        "define INNER\n"
        "inner-body: not-a-real-target\n"
        "endef\n"
        "outer-body: also-not-real\n"
        "endef\n"
        "build:\n"
        "\techo hi\n"
    )
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("build",)
    assert facts.has_define is True


def test_space_indented_endef_still_closes_the_block() -> None:
    # A leading-whitespace-indented `endef` is valid GNU Make syntax.
    # Checking indentation before the in-block define/endef check would
    # hide it, leaving the parser stuck "inside" a phantom unclosed block
    # for the rest of the file -- silently losing every real target after it.
    text = "define HELP_TEXT\nsome text\n   endef\nbuild:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("build",)


def test_hyphenated_target_name_starting_with_define_is_not_a_directive() -> None:
    # A \b word-boundary check (the original implementation) matches at a
    # word-to-hyphen transition too, so a real target literally named
    # "define-thing" would be misread as starting a define block. Requiring
    # whitespace-or-end-of-line after the keyword avoids the false positive.
    text = "define-thing:\n\techo hi\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("define-thing",)
    assert facts.has_define is False


def test_unterminated_define_block_does_not_scale_quadratically() -> None:
    # DEC-DEF-002 (ReDoS hardening): an untrusted, unterminated define
    # block must degrade to "rest of file is opaque" in linear time. This
    # is a real, previously-exploitable regression class: a whole-text
    # regex with unbounded lazy matching across an unterminated block was
    # empirically O(n^2) (tens of seconds on a ~20K-line adversarial
    # Makefile). Assert a generous, CI-safe wall-clock bound rather than
    # asserting a specific complexity class directly.
    import time

    text = "define X\n" + ("body line\n" * 20000)  # no matching endef
    start = time.monotonic()
    facts = machinery.parse_makefile(text)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"parse_makefile took {elapsed:.2f}s on an unterminated define block"
    assert facts.confidence == "low"


def test_strip_define_blocks_is_directly_testable_and_reused_by_both_parsers() -> None:
    # machinery.strip_define_blocks is the single shared implementation;
    # confirm its own return contract directly, not just through
    # parse_makefile's downstream behavior.
    cleaned, had_define = machinery.strip_define_blocks(
        "define X\nUsage: make test\nendef\nbuild:\n\techo hi\n"
    )
    assert had_define is True
    assert "Usage" not in cleaned
    assert "build:" in cleaned


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
    assert facts.has_define is False


def test_blank_lines_and_top_level_comments_are_skipped() -> None:
    text = "\n# top-level comment\n\nbuild:\n\techo hi\n\n# trailing comment\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("build",)


def test_makefile_facts_targets_is_a_sorted_deduplicated_tuple() -> None:
    text = "b: a\n\techo b\na:\n\techo a\na:\n\techo a again\n"
    facts = machinery.parse_makefile(text)
    assert facts.targets == ("a", "b")
