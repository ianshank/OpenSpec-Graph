"""``openspec_graph.repo_io`` and ``openspec_graph.thresholds``: the two modules
split out of ``detect.py``, and the re-export contract that makes the split
invisible to every existing caller.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from openspec_graph import detect, repo_io, thresholds


def test_read_text_or_none_returns_none_and_logs_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A file that exists but cannot be read (EACCES, EIO) is 'absent', never a
    traceback -- the same posture as a directory or FIFO in its place. Patched
    rather than chmod'd: as root, chmod 000 still reads fine."""
    target = tmp_path / "Makefile"
    target.write_text("all:\n\t@true\n", encoding="utf-8")

    def refuse(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", refuse)
    with caplog.at_level(logging.DEBUG, logger="planlint.detect"):
        assert repo_io.read_text_or_none(target, "Makefile") is None
    assert any("could not read" in record.getMessage() for record in caplog.records)


def test_read_text_or_none_consumes_a_bom(tmp_path: Path) -> None:
    target = tmp_path / "pyproject.toml"
    target.write_bytes(b"\xef\xbb\xbf[tool]\n")
    assert repo_io.read_text_or_none(target, "pyproject") == "[tool]\n"


@pytest.mark.parametrize(
    "name",
    [
        "to_posix_relative",
        "read_text_or_none",
        "ThresholdSource",
        "find_threshold",
        "as_threshold_number",
        "scoped_fail_under",
        "read_ini_fail_under",
        "THRESHOLD_MIN",
        "THRESHOLD_MAX",
        "COVERAGE_REPORT_TABLE",
    ],
)
def test_detect_re_exports_the_same_object(name: str) -> None:
    """Backwards compatibility is identity, not a copy: a monkeypatch on the
    source module must be seen through ``detect``, and vice versa for the
    private aliases the existing tests patch."""
    source = repo_io if hasattr(repo_io, name) else thresholds
    assert getattr(detect, name) is getattr(source, name)


def test_private_aliases_still_resolve_for_existing_patch_sites() -> None:
    assert detect._threshold is thresholds.find_threshold
    assert detect._read_ini_fail_under is thresholds.read_ini_fail_under
    # The public surface stays what it was: the formerly private helpers are
    # reachable by their old underscore names, not promoted into __all__.
    assert set(detect.__all__) >= {"ThresholdSource", "read_text_or_none", "to_posix_relative"}
    assert "find_threshold" not in detect.__all__
