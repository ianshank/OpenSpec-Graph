"""Every `_Verified by:` test citation in this repo's own specs resolves.

This project exists to fail a build when a spec cites machinery the repository
does not have. Its own specs cite *tests* the same way, via
``_Verified by:_ `pytest -k <selector>` `` — and until this guard existed,
nothing checked those. An adversarial review found that twenty-one distinct
selectors across two change packages named tests that did not exist, several
of them asserting the test "already exists". A spec-governance tool cannot
ship with that particular lie in its own tree.

A selector resolves when at least one test *function name* defined under
``tests/`` contains it as a substring. That is deliberately narrower than what
``pytest -k`` accepts: ``-k`` matches against the whole node id, so a real
selector could also match a module name, a class, or a parametrised case id.
This guard would reject such a selector as unresolved.

The narrowing is the useful direction. Every citation in this repository names
a test function, that is the convention worth enforcing, and a guard that also
accepted module and parameter names could be satisfied by a selector matching
nothing a reader would recognise as the cited test. A false rejection here
costs one rewritten citation; a false acceptance costs the property the guard
exists for. If a citation ever legitimately needs a parametrised case id, widen
this deliberately rather than loosening it to full node ids.

Names are read from the AST rather than by running pytest once per selector,
which keeps the whole guard well under a second.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_GLOB = "openspec/changes/*/specs/*/spec.md"

# `_Verified by:_ `pytest -k selector` ...` — the citation form every change
# package in this repository uses. The selector may be bare or quoted, and may
# be a boolean expression ("a or b", "a and not b").
_PYTEST_CITATION = re.compile(r"pytest\s+-k\s+(\"[^\"]+\"|'[^']+'|[^\s`]+)")

# Identifiers inside a selector expression that are actual test-name fragments,
# as opposed to pytest's own boolean operators.
_KEYWORD_OPERATORS = {"and", "or", "not"}


def _collected_test_names() -> set[str]:
    """Every test function name defined under tests/, read statically."""
    names: set[str] = set()
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test"
            ):
                names.add(node.name)
    return names


def _citations() -> list[tuple[Path, str]]:
    """(spec path, selector token) for every pytest citation in every spec."""
    found: list[tuple[Path, str]] = []
    for spec in sorted(REPO_ROOT.glob(SPEC_GLOB)):
        text = spec.read_text(encoding="utf-8")
        for raw in _PYTEST_CITATION.findall(text):
            selector = raw.strip("\"'")
            for token in selector.split():
                if token in _KEYWORD_OPERATORS:
                    continue
                found.append((spec, token.strip("()")))
    return found


def test_the_spec_corpus_actually_contains_citations() -> None:
    """Guard the guard: if the citation regex or the spec layout ever changes,
    this test file would otherwise pass by checking nothing at all."""
    citations = _citations()

    assert len(citations) > 20, (
        f"only {len(citations)} pytest citations found across {SPEC_GLOB}; "
        "the citation format probably changed and this guard has gone blind"
    )


def test_every_spec_test_citation_resolves_to_a_real_test() -> None:
    """The property itself: no spec may cite a test that does not exist."""
    known = _collected_test_names()
    unresolved: list[str] = []

    for spec, token in _citations():
        if not any(token in name for name in known):
            unresolved.append(f"{spec.relative_to(REPO_ROOT)} cites `pytest -k {token}`")

    assert not unresolved, (
        "spec(s) cite tests that do not exist — the same class of drift this "
        "tool fails other repositories for:\n  " + "\n  ".join(sorted(unresolved))
    )


@pytest.mark.parametrize(
    "selector,expected",
    [
        ("pytest -k test_alpha", ["test_alpha"]),
        ('pytest -k "test_alpha"', ["test_alpha"]),
        ('pytest -k "test_alpha or test_beta"', ["test_alpha", "test_beta"]),
        ('pytest -k "test_alpha and not test_beta"', ["test_alpha", "test_beta"]),
    ],
)
def test_selector_parsing_handles_the_forms_specs_actually_use(
    selector: str, expected: list[str]
) -> None:
    """Non-success criterion: a parser that silently extracted nothing from a
    quoted or boolean selector would make the guard above vacuously green for
    exactly the citations most likely to be wrong."""
    raw = _PYTEST_CITATION.findall(selector)
    assert raw, f"no citation parsed out of {selector!r}"

    tokens = [
        token.strip("()")
        for token in raw[0].strip("\"'").split()
        if token not in _KEYWORD_OPERATORS
    ]
    assert tokens == expected
