"""Structurally parse Makefile text without ever invoking `make`.

Pure, stdlib-only, no I/O of its own -- detect.py reads the Makefile and
hands the text in as a string. R-MP-2 (non-negotiable, DEC-MP-001): this
module MUST NEVER import or call subprocess, os.system, or any process-
execution mechanism, at any confidence level. GNU Make evaluates
``$(shell ...)`` calls outside a recipe body at parse/read time,
unconditionally -- so shelling out to a real `make` to inspect an untrusted
target repo's Makefile is unsafe under any flag combination. Safety here is
structural (the parser only ever does str.splitlines()/str.split()/re
operations on the text it is given), not a runtime guard -- see
tests/test_machinery.py's non-execution test and
tests/test_decomposition.py's static import guard.
"""

from __future__ import annotations

import dataclasses
import re

__all__ = ["MakefileFacts", "parse_makefile"]

# GNU Make's built-in special targets. A leading '.' must be part of the
# tokenizer's accepted target-name characters for any of these to ever be
# visible to this filter in the first place.
_SPECIAL_TARGETS = frozenset(
    {
        ".PHONY",
        ".DEFAULT_GOAL",
        ".SUFFIXES",
        ".PRECIOUS",
        ".INTERMEDIATE",
        ".SECONDARY",
        ".DELETE_ON_ERROR",
        ".EXPORT_ALL_VARIABLES",
        ".NOTPARALLEL",
        ".ONESHELL",
        ".POSIX",
        ".SILENT",
        ".IGNORE",
    }
)

# A rule line: one or more whitespace-separated target names, a single or
# double colon (not followed by '=', which would make it a `:=`/`::=`
# variable assignment instead), then prerequisites/opaque text.
_RULE_LINE = re.compile(r"^([^:\s][^:]*?)\s*::?(?!=)\s*(.*)$")
_VAR_EXPANSION = re.compile(r"\$[({]")
_DIRECTIVE_PREFIXES = ("include ", "-include ", "sinclude ")
_CONDITIONAL_PREFIXES = ("ifeq", "ifneq", "ifdef", "ifndef")


@dataclasses.dataclass(frozen=True)
class MakefileFacts:
    """Structural facts extracted from Makefile text."""

    targets: tuple[str, ...]
    has_include: bool
    has_conditional: bool
    unresolved_count: int

    @property
    def confidence(self) -> str:
        """'low' if this parser saw a construct it cannot fully resolve."""
        if self.has_include or self.has_conditional or self.unresolved_count > 0:
            return "low"
        return "high"


def parse_makefile(text: str) -> MakefileFacts:
    targets: set[str] = set()
    has_include = False
    has_conditional = False
    unresolved_count = 0

    for raw_line in text.splitlines():
        if raw_line[:1] in ("\t", " "):
            continue  # recipe body line: opaque text only, never interpreted
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(_DIRECTIVE_PREFIXES) or line == "include":
            has_include = True
            continue
        if line.startswith(_CONDITIONAL_PREFIXES):
            has_conditional = True
            continue
        if line.startswith(("else", "endif")):
            continue  # conditional control lines never declare targets

        match = _RULE_LINE.match(line)
        if not match:
            continue
        for name in match.group(1).split():
            if _VAR_EXPANSION.search(name):
                unresolved_count += 1  # never guess what a $(VAR) expands to
                continue
            if "%" in name:
                continue  # pattern rule (DEC-MP-004): excluded by design
            if name in _SPECIAL_TARGETS:
                continue
            targets.add(name)

    return MakefileFacts(
        targets=tuple(sorted(targets)),
        has_include=has_include,
        has_conditional=has_conditional,
        unresolved_count=unresolved_count,
    )
