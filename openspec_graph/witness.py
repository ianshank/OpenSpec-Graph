"""Witness store: proof a stage actually ran (CP-WM).

Unlike ``dialect_card.py``/``ledger.py``/``mermaid.py`` (whose
``docs/hooks.md`` recipe requires zero file I/O), this module both writes
(the ``witness`` CLI verb) and reads (``validate --require-witness``) --
kept as one module because both sides must agree on the exact wire format
and hash algorithm; splitting them would just force two modules to agree on
a shared contract, more drift-risk than benefit at this size. This is a
deliberate deviation from the "pure derived-output module" recipe, not an
oversight.

A witness is a content-addressed JSON file: its filename is the sha256 hex
digest of its own serialized bytes, so verifying a witness is as cheap as
recomputing the hash and comparing it to the filename -- no signature, no
chain, just tamper/corruption detection (``DEC-WM-010``). ``load_witnesses``
fails closed: any file that can't be read, doesn't parse, doesn't match its
own filename hash, carries an unrecognized ``schema_version``, or has a
non-finite ``coverage`` is silently skipped, never raised and never treated
as a passing witness (``DEC-WM-009``/``DEC-WM-018``). ``write_witness``
writes atomically (temp file, then ``os.replace``) so a concurrently-running
reader never observes a partially-written file (``DEC-WM-012``).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

WITNESS_SCHEMA_VERSION = 1
WITNESS_DIR_NAME = ".planlint/witnesses"

__all__ = [
    "WITNESS_DIR_NAME",
    "WITNESS_SCHEMA_VERSION",
    "Witness",
    "compute_hash",
    "load_witnesses",
    "matching_witnesses",
    "serialize",
    "write_witness",
]


@dataclasses.dataclass(frozen=True)
class Witness:
    """One recorded proof that ``stage`` ran, at ``sha``, with this outcome.

    ``recorded_at`` (ISO-8601 UTC) is informational/debugging only -- never
    load-bearing for selection (``DEC-WM-019``: no "most recent wins"
    tie-break, since that would trust wall-clock time across potentially
    different, clock-skewed CI runners).
    """

    schema_version: int
    stage: str
    exit_code: int
    coverage: float | None
    sha: str
    recorded_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "stage": self.stage,
            "exit_code": self.exit_code,
            "coverage": self.coverage,
            "sha": self.sha,
            "recorded_at": self.recorded_at,
        }


def compute_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def serialize(witness: Witness) -> bytes:
    """Canonical JSON bytes -- the exact bytes written to disk and hashed.

    Sorted keys, compact separators: the same ``Witness`` always serializes
    to the same bytes, so ``compute_hash`` is deterministic and the on-disk
    file's content is literally what gets hashed (no re-serialization step
    that could silently diverge from what was written).
    """
    return json.dumps(witness.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_witness(root: Path, witness: Witness) -> Path:
    """Write ``witness`` under ``root/.planlint/witnesses/<hash>.json``, atomically.

    Writes to a temp file in the same directory first, then ``os.replace()``s
    it into place -- a concurrently-running ``load_witnesses()`` call (an
    overlapping second ``validate --require-witness``, say) can never observe
    a partially-written file (``DEC-WM-012``). Content-addressing makes this
    idempotent: writing the same ``Witness`` twice produces the same target
    path with the same bytes, harmlessly.
    """
    directory = root / WITNESS_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    payload = serialize(witness)
    target = directory / f"{compute_hash(payload)}.json"
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def _load_one(path: Path) -> Witness | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if compute_hash(payload) != path.stem:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("schema_version") != WITNESS_SCHEMA_VERSION:
        return None
    coverage = data.get("coverage")
    if coverage is not None:
        if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not math.isfinite(coverage):
            return None
        coverage = float(coverage)
    try:
        return Witness(
            schema_version=int(data["schema_version"]),
            stage=str(data["stage"]),
            exit_code=int(data["exit_code"]),
            coverage=coverage,
            sha=str(data["sha"]),
            recorded_at=str(data["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_witnesses(root: Path) -> tuple[Witness, ...]:
    """Every valid witness under ``root/.planlint/witnesses/``.

    A missing directory returns ``()``. Fails closed per-file, never
    per-store: one corrupt/malformed/hash-mismatched/wrong-schema-version
    file is skipped like any other non-declaring file, mirroring
    ``detect._adrs()``'s established discipline -- it can't crash every CLI
    verb that calls ``detect.profile()``, and it can't silently count as a
    pass either.
    """
    directory = root / WITNESS_DIR_NAME
    if not directory.is_dir():
        return ()
    witnesses: list[Witness] = []
    for path in sorted(directory.glob("*.json")):
        witness = _load_one(path)
        if witness is not None:
            witnesses.append(witness)
    return tuple(witnesses)


def matching_witnesses(witnesses: Sequence[Witness], stage: str, sha: str) -> tuple[Witness, ...]:
    """Every witness recorded for ``stage`` at exactly ``sha``, any exit code.

    No single "best match" -- callers decide what "matches" means for their
    own check (``DEC-WM-019``): W001 asks whether any result has
    ``exit_code == 0``; W002 asks whether every such result clears the
    coverage floor.
    """
    return tuple(w for w in witnesses if w.stage == stage and w.sha == sha)
