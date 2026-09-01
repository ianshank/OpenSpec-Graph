"""Rule-engine types: Finding, Rule, and severity constants.

Sits at the bottom of the rules layer. Imports the parsed-spec and stack-profile
types only for type hints (``Rule.check`` signature); performs no analysis.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable
from pathlib import Path

from .detect import StackProfile, to_posix_relative
from .parse import ParsedSpec

__all__ = ["ERROR", "INFO", "WARN", "Finding", "ParsedSpec", "Rule", "StackProfile"]

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

# Make targets a spec may cite without them existing yet in the Makefile.
GENERIC_STAGES = {"ci", "test", "validate", "lint", "coverage"}


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    path: Path | None = None
    line: int = 0
    subject: str = ""  # entity a tree-scoped finding is about, e.g. an invariant id (G006)

    def as_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "path": str(self.path) if self.path else None,
            "line": self.line,
            "subject": self.subject,
        }

    def render(self, root: Path | None = None) -> str:
        where = ""
        if self.path:
            shown = to_posix_relative(self.path, root)
            where = f"{shown}:{self.line}: " if self.line else f"{shown}: "
        return f"{self.severity:5s} {self.rule}  {where}{self.message}"


@dataclasses.dataclass(frozen=True)
class Rule:
    ident: str
    severity: str
    dialects: tuple[str, ...]  # ("*",) for any
    summary: str
    check: Callable[[ParsedSpec, StackProfile], Iterable[str]]

    def applies(self, dialect: str) -> bool:
        return "*" in self.dialects or dialect in self.dialects
