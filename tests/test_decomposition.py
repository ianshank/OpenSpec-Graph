"""Decomposition guard tests (change package: decompose-god-files).

These lock the public contract BEFORE the production modules are split, so a
refactor that drifts the public import surface or the CLI/graph/rules JSON
output fails `make test`. Path-normalized so they are reproducible across temp
dirs.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent
FX = REPO_ROOT / "tests" / "fixtures"

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
