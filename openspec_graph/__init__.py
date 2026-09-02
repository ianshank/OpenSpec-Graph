"""openspec-graph — port an OpenSpec discipline onto a cloned repository.

The framework detects what the target repo already does (build stages,
coverage floor location, invariant source, spec dialect) and then enforces
the spec conventions mechanically instead of by review prose.
"""

from __future__ import annotations

# The single source of truth for the version. `pyproject.toml` reads this
# attribute via setuptools' `dynamic`/`attr:` mechanism rather than carrying
# its own literal -- two literals with nothing binding them is the same drift
# class `tests/test_rule_registry_docs.py` exists for, and a release is the
# worst place to discover it (DEC-SD-009).
__version__ = "0.2.0"

from .detect import StackProfile, detect_dialect, profile
from .graph import NoOpenSpecTreeError, build_graph
from .parse import Criterion, ParsedSpec, Requirement, parse_spec
from .rules import RULES, Finding, evaluate, rule_table
from .scaffold import plan_change, plan_init

__all__ = [
    "RULES",
    "Criterion",
    "Finding",
    "NoOpenSpecTreeError",
    "ParsedSpec",
    "Requirement",
    "StackProfile",
    "__version__",
    "build_graph",
    "detect_dialect",
    "evaluate",
    "parse_spec",
    "plan_change",
    "plan_init",
    "profile",
    "rule_table",
]
