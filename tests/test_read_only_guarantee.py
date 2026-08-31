"""The read-only guarantee, proven rather than asserted (XTV M1).

``detect.py``'s module docstring claims detection is read-only by contract so
``planlint detect`` is always safe to run against an unfamiliar clone. Until
now that claim rested on a docstring and on the absence of an obvious write.
These tests make it falsifiable: the process-execution surface and the socket
surface are patched to raise, and the target tree is fingerprinted before and
after every read-only verb.

Precedent: ``tests/test_machinery.py`` already patches ``subprocess.run`` /
``Popen`` to raise for the Makefile parser (AC-MP-2). This generalises that
approach from one module to the whole CLI surface.
"""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
from pathlib import Path

import pytest

from openspec_graph import cli
from tests.support import write_spec

READ_ONLY_VERBS: tuple[tuple[str, ...], ...] = (
    ("detect",),
    ("detect", "--json"),
    ("validate", "--fail-on", "ERROR"),
    ("validate", "--json"),
    ("graph", "--format", "json"),
)

SPEC = """\
# Spec: Demo

> **Change:** `demo`
> **Version:** 1.0.0
> **Status:** APPROVED

## Problem Statement

Prose.

## Requirements

- R-DM-1: The system MUST do the thing.

## Acceptance Criteria

- [x] **AC-DM-1 (non-success):** A malformed input is rejected, not accepted. (R-DM-1)
  _Verified by:_ `pytest -k test_demo` · stage: `make test`

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-DM-1 |
"""


def _target(tmp_path: Path) -> Path:
    """A minimal but complete target repo: machinery + one valid spec."""
    (tmp_path / "Makefile").write_text(
        ".PHONY: test ci\ntest: ## t\n\tpytest\nci: test ## c\n\t@echo ok\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n\n[tool.coverage.report]\nfail_under = 90\n'
    )
    write_spec(tmp_path, "demo", "demo-capability", SPEC)
    return tmp_path


def _fingerprint(root: Path) -> dict[str, tuple[int, int, str]]:
    """Content hash *and* size *and* mtime for every file under ``root``.

    mtime is deliberately included: a verb that writes a file and then restores
    its bytes would leave the content hash unchanged, so content alone cannot
    detect a write-then-restore. See AC-XTV-3.
    """
    out: dict[str, tuple[int, int, str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        st = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[path.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns, digest)
    return out


@pytest.mark.parametrize("argv", READ_ONLY_VERBS, ids=lambda a: "-".join(a))
def test_verbs_never_invoke_a_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...]) -> None:
    """AC-XTV-1: no read-only verb shells out, at any confidence level.

    An import guard cannot prove this -- ``subprocess`` is stdlib, and
    ``os.system`` bypasses it entirely -- so every execution entry point is
    patched to raise instead.
    """
    root = _target(tmp_path)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a read-only verb attempted to execute a subprocess")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "call", _boom, raising=False)
    monkeypatch.setattr(subprocess, "check_output", _boom, raising=False)
    monkeypatch.setattr(os, "system", _boom)
    monkeypatch.setattr(os, "popen", _boom, raising=False)

    assert cli.main(["--target", str(root), *argv]) in (0, 1)


def test_the_subprocess_guard_can_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard above is only evidence if it detects a real call (mutation check)."""
    root = _target(tmp_path)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("subprocess attempted")

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(AssertionError, match="subprocess attempted"):
        subprocess.run(["echo", "hi"], check=False)
    assert root.exists()


@pytest.mark.parametrize("argv", READ_ONLY_VERBS, ids=lambda a: "-".join(a))
def test_verbs_never_open_a_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...]) -> None:
    """AC-XTV-2: no read-only verb opens a network connection."""
    root = _target(tmp_path)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a read-only verb attempted to open a socket")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)

    assert cli.main(["--target", str(root), *argv]) in (0, 1)


def test_the_socket_guard_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation check for the socket guard: a deliberate loopback connect raises.

    Loopback, not an external host -- this must stay runnable on a machine or CI
    runner with egress blocked.
    """
    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("socket attempted")

    monkeypatch.setattr(socket, "create_connection", _boom)
    with pytest.raises(AssertionError, match="socket attempted"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.01)


@pytest.mark.parametrize("argv", READ_ONLY_VERBS, ids=lambda a: "-".join(a))
def test_target_tree_hash_is_unchanged_and_restore_does_not_pass(tmp_path: Path, argv: tuple[str, ...]) -> None:
    """AC-XTV-3: the target tree is byte- and mtime-identical after every verb."""
    root = _target(tmp_path)
    before = _fingerprint(root)
    assert cli.main(["--target", str(root), *argv]) in (0, 1)
    assert _fingerprint(root) == before, "a read-only verb modified the target tree"


def test_a_write_then_restore_is_still_detected(tmp_path: Path) -> None:
    """AC-XTV-3 (second half): content-only comparison would pass this; ours must not.

    Rewriting identical bytes leaves the sha256 unchanged, so a fingerprint built
    from content alone cannot see it. Including mtime is what closes that hole.
    """
    root = _target(tmp_path)
    before = _fingerprint(root)

    victim = root / "Makefile"
    original = victim.read_bytes()
    victim.write_bytes(b"# transient\n")
    victim.write_bytes(original)  # byte-identical restore

    after = _fingerprint(root)
    assert {k: v[2] for k, v in after.items()} == {k: v[2] for k, v in before.items()}, (
        "precondition: the restore must leave content hashes identical"
    )
    assert after != before, "a write-then-restore must still be detected"
