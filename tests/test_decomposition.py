"""Decomposition guard tests (change package: decompose-god-files).

These lock the public contract BEFORE the production modules are split, so a
refactor that drifts the public import surface or the CLI/graph/rules JSON
output fails `make test`. Path-normalized so they are reproducible across temp
dirs.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG = REPO_ROOT / "openspec_graph"
FX = REPO_ROOT / "tests" / "fixtures"

# Modules created by this change package. Each must stay stdlib-only (R-DG-3) and
# obey the import boundary: no importing cli or graph (R-DG-5).
_NEW_MODULES = [
    "scaffold_templates",
    "parse_semantics",
    "parse_model",
    "parse_harness",
    "parse_upstream",
    "rule_types",
    "rules_generic",
    "rules_harness",
    "rules_upstream",
]

# Modules that must NOT import cli or graph (the orchestration/output layers).
# cli.py and __init__.py are the expected hubs and are exempt.
_BOUNDARY_EXEMPT = {"cli", "__init__"}

# Path-normalized SHA-256 of validate --json / graph --format json / rules --json
# for the canonical fixture repo (tests/fixtures/). Captured before the split;
# any drift after decomposition fails AC-DG-2.
_EXPECTED_HASHES = {
    "validate": "0a810b4f791fa5684dbf384df7ab626ddf96c3b62fcd9d8299dc8d774a3b82e0",
    "graph": "6a63cc66d2e319f9fde85a37f46f333429c6be9989be5d5eb6686183afedfa9c",
    "rules": "e25ad6cd262a52447cd11ada2c96494b3a7af2ca83cb8e6af6911f20b719540f",
}


def _build_repo(root: Path) -> None:
    (root / "Makefile").write_text((FX / "Makefile").read_text(encoding="utf-8"))
    (root / "pyproject.toml").write_text((FX / "pyproject.toml").read_text(encoding="utf-8"))
    for change, cap, fname in [
        ("c1", "cap", "good_harness.md"),
        ("c2", "cap2", "good_upstream.md"),
    ]:
        sp = root / "openspec" / "changes" / change / "specs" / cap / "spec.md"
        sp.parent.mkdir(parents=True)
        sp.write_text((FX / fname).read_text(encoding="utf-8"))


def _run_cli(root: Path, *args: str) -> str:
    r = subprocess.run(
        [sys.executable, "-m", "openspec_graph.cli", "--target", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, f"{' '.join(args)} failed: {r.stderr}"
    return r.stdout.replace(str(root), "<ROOT>")


def _outputs(root: Path) -> dict[str, str]:
    return {
        "validate": _run_cli(root, "validate", "--json"),
        "graph": _run_cli(root, "graph", "--format", "json"),
        "rules": _run_cli(root, "rules", "--json"),
    }


def _imported_roots(path: Path) -> set[str]:
    """Top-level module names imported by a .py file (relative + absolute)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            # relative imports are intra-package; not a stdlib concern
            roots.add(node.module.split(".")[0])
    return roots


# --- AC-DG-1: public import surface unchanged -------------------------------


def test_public_import_compatibility() -> None:
    # Every symbol tests and call sites import must remain importable from the
    # same paths after the facade split.
    from openspec_graph import build_graph  # noqa: F401
    from openspec_graph.parse import (  # noqa: F401
        Criterion,
        ParsedSpec,
        Requirement,
        parse_spec,
    )
    from openspec_graph.rules import (  # noqa: F401
        Finding,
        Rule,
        evaluate,
        rule_table,
    )


# --- AC-DG-2: byte-identical CLI/graph/rules JSON output --------------------


def test_output_byte_identical() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _build_repo(root)
        outs = _outputs(root)
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in outs.items()}
    assert hashes == _EXPECTED_HASHES, (
        "CLI/graph/rules JSON drifted after decomposition.\n"
        f"expected: {_EXPECTED_HASHES}\n"
        f"actual:   {hashes}\n"
    )


# --- AC-DG-3 (non-success): rules --json ordering must be stable ------------


def test_rules_json_ordering_stable() -> None:
    # Re-evaluating the same fixture repo twice must yield byte-identical
    # rules --json (stable ordering). A moved rule that changes ordering fails.
    with TemporaryDirectory() as td:
        root = Path(td)
        _build_repo(root)
        first = _run_cli(root, "rules", "--json")
        second = _run_cli(root, "rules", "--json")
    assert first == second, "rules --json must be byte-identical across runs"
    # And it must match the canonical hash.
    assert hashlib.sha256(first.encode()).hexdigest() == _EXPECTED_HASHES["rules"]


# --- AC-DG-4: new modules import only stdlib (no third-party deps) ----------


def test_new_modules_stdlib_only() -> None:
    stdlib = set(sys.stdlib_module_names)
    for name in _NEW_MODULES:
        roots = _imported_roots(PKG / f"{name}.py")
        third_party = roots - stdlib
        assert not third_party, (
            f"{name}.py imports non-stdlib modules: {sorted(third_party)} (R-DG-3)"
        )


# --- AC-DG-5: shared helper is not duplicated inline ------------------------


def test_helpers_not_duplicated_inline() -> None:
    # _write_spec must be imported from tests.support, not redeclared.
    for fname in ("test_enterprise.py", "test_ci_hardening.py"):
        path = REPO_ROOT / "tests" / fname
        tree = ast.parse(path.read_text(encoding="utf-8"))
        redeclared = [
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_write_spec"
        ]
        assert not redeclared, (
            f"{fname} redeclares _write_spec inline; import it from tests.support "
            "instead (R-DG-4)"
        )


# --- AC-DG-6 (non-success): parser/rule modules must not import cli or graph


def test_import_boundary_discipline() -> None:
    # No module except cli.py and __init__.py may import cli or graph.
    offenders: dict[str, set[str]] = {}
    for path in PKG.glob("*.py"):
        stem = path.stem
        if stem in _BOUNDARY_EXEMPT:
            continue
        roots = _imported_roots(path)
        bad = roots & {"cli", "graph"}
        if bad:
            offenders[stem] = bad
    assert not offenders, (
        f"modules import cli/graph (forbidden below the hub layer): {offenders} (R-DG-5)"
    )
