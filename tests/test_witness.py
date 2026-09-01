"""Tests for openspec_graph.witness (change package: add-witness-mode).

Pure, no CLI/subprocess -- mirrors test_ledger.py's/test_dialect_card.py's
style. Direct function calls against openspec_graph.witness, not through
detect.profile() (that's covered separately in test_graft.py, since it also
exercises the git-dependent _current_sha() lazy wiring).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from openspec_graph import witness
from openspec_graph.witness import Witness
from tests import support

# Windows needs Administrator rights or Developer Mode to create any symlink
# at all -- probed once, at this module's import time, not assumed from
# sys.platform, so a Windows box that does have one of those enabled still
# runs this test.
_CAN_SYMLINK = support.supports_symlinks()

SHA = "a" * 40


def _witness(**overrides: object) -> Witness:
    fields: dict[str, object] = {
        "schema_version": witness.WITNESS_SCHEMA_VERSION,
        "stage": "test",
        "exit_code": 0,
        "coverage": 97.5,
        "sha": SHA,
        "recorded_at": "2026-01-01T00:00:00Z",
    }
    fields.update(overrides)
    return Witness(**fields)  # type: ignore[arg-type]


def _write_raw(root: Path, data: dict[str, object]) -> Path:
    """Write a witness file directly from a dict, bypassing write_witness() --
    simulates a hand-edited, tampered, or cross-version file, matching
    DEC-WM-018's own reasoning for validating at load time, not just record
    time."""
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    directory = root / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{witness.compute_hash(payload)}.json"
    path.write_bytes(payload)
    return path


def test_witness_round_trips_through_write_and_load(tmp_path: Path) -> None:
    w = _witness()
    witness.write_witness(tmp_path, w)
    assert witness.load_witnesses(tmp_path) == (w,)


def test_witness_filename_is_the_sha256_of_its_own_content(tmp_path: Path) -> None:
    path = witness.write_witness(tmp_path, _witness())
    assert path.stem == hashlib.sha256(path.read_bytes()).hexdigest()


def test_write_witness_creates_the_planlint_witnesses_directory_if_absent(tmp_path: Path) -> None:
    assert not (tmp_path / witness.WITNESS_DIR_NAME).exists()
    witness.write_witness(tmp_path, _witness())
    assert (tmp_path / witness.WITNESS_DIR_NAME).is_dir()


def test_write_witness_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A concurrently-running load_witnesses() must never observe a
    # partially-written file (DEC-WM-012) -- proven by verifying the only
    # operation that makes the file appear at its final path is a single
    # rename of an already-fully-written temp file: nothing exists at the
    # target before that rename, and the temp file already holds the
    # complete payload when it happens.
    w = _witness()
    real_replace = os.replace
    calls: list[tuple[bytes, bool]] = []

    def spy_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        calls.append((Path(src).read_bytes(), Path(dst).exists()))
        real_replace(src, dst)

    monkeypatch.setattr(witness.os, "replace", spy_replace)  # type: ignore[attr-defined]
    path = witness.write_witness(tmp_path, w)
    assert len(calls) == 1
    payload_at_rename_time, target_existed_before = calls[0]
    assert payload_at_rename_time == witness.serialize(w)
    assert target_existed_before is False
    assert path.read_bytes() == witness.serialize(w)


def test_write_witness_cleans_up_the_temp_file_and_reraises_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(src: object, dst: object) -> None:
        raise OSError("simulated rename failure")

    monkeypatch.setattr(witness.os, "replace", boom)  # type: ignore[attr-defined]
    with pytest.raises(OSError, match="simulated rename failure"):
        witness.write_witness(tmp_path, _witness())
    directory = tmp_path / witness.WITNESS_DIR_NAME
    leftover = list(directory.glob("*"))
    assert leftover == [], f"a failed write must not leave a temp file behind: {leftover}"


def test_load_witnesses_returns_empty_tuple_when_the_directory_is_absent(tmp_path: Path) -> None:
    assert witness.load_witnesses(tmp_path) == ()


@pytest.mark.skipif(not _CAN_SYMLINK, reason="platform/user lacks symlink-creation privilege")
def test_load_witnesses_skips_a_dangling_symlink_without_raising(tmp_path: Path) -> None:
    # glob("*.json") lists directory entries by name pattern only, not
    # readability -- mirrors the exact class of bug fixed for ADR discovery
    # this session (detect._adrs()'s directory branch).
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    (directory / ("0" * 64 + ".json")).symlink_to(directory / "does-not-exist.json")
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_a_file_whose_content_does_not_match_its_filename_hash(tmp_path: Path) -> None:
    # AC-WM-16 (non-success): a tampered/corrupt witness must fail closed,
    # not raise and not be treated as a pass.
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    (directory / ("0" * 64 + ".json")).write_bytes(witness.serialize(_witness()))
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_malformed_json_without_raising(tmp_path: Path) -> None:
    payload = b"not valid json {"
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    (directory / f"{witness.compute_hash(payload)}.json").write_bytes(payload)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_valid_json_that_is_not_an_object(tmp_path: Path) -> None:
    # Well-formed JSON whose top-level value isn't a dict at all (a bare
    # array here) -- distinct from malformed JSON above; .get() would raise
    # AttributeError on this without the isinstance(data, dict) guard.
    payload = b"[1, 2, 3]"
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    (directory / f"{witness.compute_hash(payload)}.json").write_bytes(payload)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_non_utf8_bytes_without_raising(tmp_path: Path) -> None:
    # GitHub Copilot review finding on PR #14: json.loads(bytes) decodes
    # internally before parsing, and non-UTF-8 bytes raise
    # UnicodeDecodeError (a ValueError sibling, not a json.JSONDecodeError
    # subclass) directly from that step -- a real, previously-uncaught
    # violation of load_witnesses()'s "never raises" contract (R-WM-9) for
    # any hash-matching-but-non-UTF-8 file (this is content-addressed, so
    # naturally-corrupted bytes would fail the hash check first; the real
    # trigger is a hand-crafted or non-first-party-tool-written file --
    # still a real concern given .planlint/witnesses/ is part of the
    # target repo's own, potentially untrusted, working tree).
    payload = b'{"stage": "test\xc3\x28"}'  # \xc3 starts a 2-byte UTF-8
    # sequence; \x28 ("(") is not a valid continuation byte.
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    (directory / f"{witness.compute_hash(payload)}.json").write_bytes(payload)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_a_schema_version_that_is_a_bool_not_an_int(tmp_path: Path) -> None:
    # GitHub Copilot review finding on PR #14: bool is an int subclass in
    # Python (True == 1), so schema_version: true would otherwise silently
    # pass the `== WITNESS_SCHEMA_VERSION` check -- defeating the strict
    # schema-version validation DEC-WM-018 specifically added to close this
    # exact bug class (the same shape as the already-fixed
    # dialect_card.diff_cards() schema bug).
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    payload = witness.serialize(_witness(schema_version=True))
    (directory / f"{witness.compute_hash(payload)}.json").write_bytes(payload)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_an_exit_code_that_is_a_bool_not_an_int(tmp_path: Path) -> None:
    # Same bug class as schema_version above, one line down in the same
    # function -- not itself flagged by the review, but exit_code == 0
    # means "the assertion held" in W001's own logic, so silently coercing
    # exit_code: false to 0 would be a stricter, more consequential version
    # of the identical type-confusion bug, not a hypothetical one.
    directory = tmp_path / witness.WITNESS_DIR_NAME
    directory.mkdir(parents=True)
    payload = witness.serialize(_witness(exit_code=False))
    (directory / f"{witness.compute_hash(payload)}.json").write_bytes(payload)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_a_file_missing_a_required_field_without_raising(tmp_path: Path) -> None:
    data = {"schema_version": witness.WITNESS_SCHEMA_VERSION, "stage": "test", "exit_code": 0}
    _write_raw(tmp_path, data)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_a_file_with_an_unrecognized_schema_version(tmp_path: Path) -> None:
    data = {
        "schema_version": witness.WITNESS_SCHEMA_VERSION + 1,
        "stage": "test",
        "exit_code": 0,
        "coverage": 97.0,
        "sha": SHA,
        "recorded_at": "2026-01-01T00:00:00Z",
    }
    _write_raw(tmp_path, data)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_a_file_with_non_finite_coverage(tmp_path: Path) -> None:
    data = {
        "schema_version": witness.WITNESS_SCHEMA_VERSION,
        "stage": "test",
        "exit_code": 0,
        "coverage": float("nan"),
        "sha": SHA,
        "recorded_at": "2026-01-01T00:00:00Z",
    }
    _write_raw(tmp_path, data)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_skips_a_file_with_a_boolean_coverage(tmp_path: Path) -> None:
    # bool is a subclass of int in Python; a JSON `true`/`false` must not be
    # silently coerced into a coverage number.
    data = {
        "schema_version": witness.WITNESS_SCHEMA_VERSION,
        "stage": "test",
        "exit_code": 0,
        "coverage": True,
        "sha": SHA,
        "recorded_at": "2026-01-01T00:00:00Z",
    }
    _write_raw(tmp_path, data)
    assert witness.load_witnesses(tmp_path) == ()


def test_load_witnesses_accepts_a_witness_with_no_recorded_coverage(tmp_path: Path) -> None:
    w = _witness(coverage=None)
    witness.write_witness(tmp_path, w)
    assert witness.load_witnesses(tmp_path) == (w,)


def test_matching_witnesses_filters_by_stage_and_sha_only_not_exit_code() -> None:
    # matching_witnesses() itself is exit-code-agnostic -- callers (W001/W002)
    # decide what "matches" means for their own check (DEC-WM-019).
    w_match = _witness()
    w_wrong_stage = _witness(stage="lint")
    w_wrong_sha = _witness(sha="b" * 40)
    w_failing = _witness(exit_code=1)
    result = witness.matching_witnesses([w_match, w_wrong_stage, w_wrong_sha, w_failing], "test", SHA)
    assert set(result) == {w_match, w_failing}
