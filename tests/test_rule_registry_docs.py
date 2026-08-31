"""Guards every prose claim about the rule registry's count or per-family id
ranges against ``rules.RULES`` itself -- the real source of truth.

Added by CP-AD after the third independent recurrence of the same drift
class in this codebase's history (``docs/architecture/c4.md`` twice, then
``rules.py``'s own module docstring): a single test, not a new tool or
Makefile target, per ``fix-adopter-artifact-drift``'s own pre-authorized
"cheapest form" once recurrence is demonstrated (DEC-AD-006).

``CHANGELOG.md`` is deliberately excluded -- its dated entries are historical
record, correct when written; a changelog is supposed to diverge from the
live count over time, and guarding it would fight its own purpose.

Pure: reads ``rules.RULES`` and doc files as plain text, no CLI/subprocess
needed (mirrors ``test_dialect_card.py``'s style).
"""

from __future__ import annotations

import re
from pathlib import Path

from openspec_graph.rules import RULES

REPO_ROOT = Path(__file__).resolve().parent.parent

_FAMILIES = (("G", "rules_generic"), ("H", "rules_harness"), ("U", "rules_upstream"))


def _family_range(prefix: str) -> tuple[str, str]:
    idents = sorted(r.ident for r in RULES if r.ident.startswith(prefix))
    return idents[0], idents[-1]


def test_readme_rules_table_matches_rules_exactly() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    found = dict(re.findall(r"^\| (G\d{3}|H\d{3}|U\d{3}) \| (ERROR|WARN) \|", text, re.MULTILINE))
    expected = {r.ident: r.severity for r in RULES}
    assert found == expected, (
        f"README.md's rules table is out of sync with rules.RULES.\n"
        f"missing/extra: {set(expected) ^ set(found)}\n"
        f"severity mismatches: {[k for k in expected if k in found and expected[k] != found[k]]}"
    )


def test_total_rule_count_matches_every_prose_claim() -> None:
    total = len(RULES)
    claims = [
        ("docs/architecture/c4.md", r"(\d+)\s+deterministic rules"),
        ("docs/agents-skills-harness.md", r"The (\d+) rules"),
        ("docs/next-steps.md", r"the (\d+) rules"),
    ]
    for doc, pattern in claims:
        text = (REPO_ROOT / doc).read_text(encoding="utf-8")
        matches = re.findall(pattern, text)
        assert matches, f"{doc}: no rule-count claim found matching {pattern!r}"
        for m in matches:
            assert int(m) == total, f"{doc} claims {m} rules; rules.RULES actually has {total}"


def test_rules_py_docstring_family_ranges_match_rules() -> None:
    text = (REPO_ROOT / "openspec_graph" / "rules.py").read_text(encoding="utf-8")
    for prefix, module in _FAMILIES:
        low, high = _family_range(prefix)
        assert f"{low}-{high}" in text, (
            f"rules.py's own module docstring doesn't claim {module} covers {low}-{high} "
            f"(the exact drift this test exists to catch)"
        )


def test_c4_module_map_family_ranges_match_rules() -> None:
    text = (REPO_ROOT / "docs" / "architecture" / "c4.md").read_text(encoding="utf-8")
    for prefix, module in _FAMILIES:
        low, high = _family_range(prefix)
        # c4.md's module map uses an en dash; tolerate either dash character.
        pattern = rf"{module}\.py\s+#\s*{re.escape(low)}[–-]{re.escape(high)}"
        assert re.search(pattern, text), (
            f"c4.md's module map doesn't claim {module}.py covers {low}-{high}"
        )
