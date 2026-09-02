"""The wheel-metadata gate catches what it claims to — `AC-LM-3`.

Why these tests are not "build the real wheel and look at it". The obvious
fail-closed criterion for the PEP 639 migration was "a build with no LICENSE
file fails". It does not: setuptools accepts a ``license-files`` glob matching
nothing and emits a wheel with no licence, silently. So the gate reads the
artifact instead — and a gate is only worth having if something proves it
rejects a bad artifact. These build synthetic wheels in-memory, one per
violation, which is both faster and stricter than hoping a real build happens
to be broken in the right way.

A single end-to-end test at the bottom runs the gate against the wheel this
repository actually produces, so the synthetic fixtures can never drift into
testing a shape setuptools no longer emits.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

from check_wheel_metadata import check_wheel, main  # noqa: E402

# Deliberately not this project's own name or version. The gate derives the
# .dist-info directory from the wheel it is handed and must not depend on
# either, so a fixture naming them would both hide that and need editing on
# every routine version bump.
DIST_INFO = "example_dist-9.9.9.dist-info"

GOOD_METADATA = """\
Metadata-Version: 2.4
Name: planlint
Version: 0.2.0
License-Expression: Apache-2.0
License-File: LICENSE
Classifier: Development Status :: 4 - Beta
"""


def _wheel(
    tmp_path: Path,
    *,
    metadata: str = GOOD_METADATA,
    license_text: str | None = "Apache License\n",
    name: str = "example_dist-9.9.9-py3-none-any.whl",
    extra: dict[str, str] | None = None,
) -> Path:
    """A minimal but structurally real wheel.

    ``extra`` writes additional archive members verbatim, for fixtures that
    need to place a file somewhere other than the licence directory.
    """
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{DIST_INFO}/METADATA", metadata)
        if license_text is not None:
            archive.writestr(f"{DIST_INFO}/licenses/LICENSE", license_text)
        for member, content in (extra or {}).items():
            archive.writestr(member, content)
    return path


def test_a_correct_wheel_passes(tmp_path: Path) -> None:
    assert check_wheel(_wheel(tmp_path), "Apache-2.0", ["LICENSE"]) == []


def test_missing_license_expression_is_caught(tmp_path: Path) -> None:
    """The core regression: a wheel built by a setuptools too old to
    understand the SPDX form would omit this key entirely."""
    metadata = GOOD_METADATA.replace("License-Expression: Apache-2.0\n", "")

    problems = check_wheel(_wheel(tmp_path, metadata=metadata), "Apache-2.0", ["LICENSE"])

    assert problems
    assert "License-Expression" in problems[0]


def test_a_mismatched_expression_is_caught(tmp_path: Path) -> None:
    """The wheel must carry the licence pyproject declares, not merely some
    licence — a silent relicensing is exactly what nobody reviews."""
    metadata = GOOD_METADATA.replace("Apache-2.0", "MIT")

    problems = check_wheel(_wheel(tmp_path, metadata=metadata), "Apache-2.0", ["LICENSE"])

    assert problems


def test_a_legacy_license_classifier_is_caught(tmp_path: Path) -> None:
    """PEP 639 forbids the pair, and setuptools>=77 rejects it. Catching it
    here means the failure is one readable line, not a build traceback."""
    metadata = GOOD_METADATA + "Classifier: License :: OSI Approved :: Apache Software License\n"

    problems = check_wheel(_wheel(tmp_path, metadata=metadata), "Apache-2.0", ["LICENSE"])

    assert any("legacy classifier" in p for p in problems)


def test_a_missing_license_file_is_caught(tmp_path: Path) -> None:
    """The exact failure the original criterion wrongly assumed the build
    itself would catch: metadata claims a licence, the archive has none."""
    problems = check_wheel(
        _wheel(tmp_path, license_text=None), "Apache-2.0", ["LICENSE"]
    )

    assert any("license-files" in p for p in problems)


def test_a_licence_outside_dist_info_does_not_satisfy_the_check(tmp_path: Path) -> None:
    """A licence shipped as package data is not a packaged licence.

    The first version of this gate matched any archive member whose path
    contained "licenses/", so a `src/licenses/LICENSE` satisfied it while
    `.dist-info/licenses/` was missing entirely — the installer registers no
    licence, and the gate reported one. Found in review of this gate's own
    pull request, which is the point: a check that cannot fail is worse than
    no check, because it is believed.
    """
    wheel = _wheel(
        tmp_path,
        license_text=None,
        extra={"src/licenses/LICENSE": "Apache License\n"},
    )

    problems = check_wheel(wheel, "Apache-2.0", ["LICENSE"])

    assert any("license-files" in p for p in problems), problems


def test_the_dist_info_directory_name_is_not_assumed(tmp_path: Path) -> None:
    """The gate reads the wheel it is handed. A differently-named
    distribution must pass on its own merits, so the anchoring fix cannot
    have hard-coded this project's own dist-info name."""
    path = tmp_path / "other_project-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("other_project-1.2.3.dist-info/METADATA", GOOD_METADATA)
        archive.writestr("other_project-1.2.3.dist-info/licenses/LICENSE", "Apache License\n")

    assert check_wheel(path, "Apache-2.0", ["LICENSE"]) == []


def test_an_empty_license_file_is_caught(tmp_path: Path) -> None:
    """A zero-byte LICENSE satisfies "the file is present" and satisfies
    nobody's lawyer."""
    problems = check_wheel(_wheel(tmp_path, license_text="   \n"), "Apache-2.0", ["LICENSE"])

    assert any("empty" in p for p in problems)


def test_a_wheel_without_metadata_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "broken-0.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("planlint/__init__.py", "")

    problems = check_wheel(path, "Apache-2.0", ["LICENSE"])

    assert any("METADATA" in p for p in problems)


# --- The CLI's own three-way exit contract ---


def test_main_exits_1_on_a_bad_wheel(tmp_path: Path) -> None:
    _wheel(tmp_path, license_text=None)

    assert main([str(tmp_path)]) == 1


def test_main_exits_0_on_a_good_wheel(tmp_path: Path) -> None:
    _wheel(tmp_path)

    assert main([str(tmp_path)]) == 0


def test_main_exits_2_when_there_is_nothing_to_check(tmp_path: Path) -> None:
    """Non-success criterion: "no wheels" must never read as "all wheels
    passed". A release job whose build step silently produced nothing would
    otherwise sail straight through this gate."""
    assert main([str(tmp_path)]) == 2


def test_main_exits_2_on_a_missing_directory(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope")]) == 2


# --- Against the real artifact ---


def test_the_real_wheel_passes_the_gate(tmp_path: Path) -> None:
    """Builds this project for real, in an isolated environment, and gates the
    result. Skips rather than fails when `build` is unavailable or the network
    is not there to resolve build requirements — a missing tool is not a
    licensing defect, and CI's release job runs this path unconditionally."""
    repo = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path), str(repo)],
        capture_output=True, text=True, check=False, encoding="utf-8",
    )
    if result.returncode != 0:
        pytest.skip(f"`python -m build` unavailable in this environment:\n{result.stderr[-400:]}")

    assert main([str(tmp_path)]) == 0
    # And the migration's own headline claim: no deprecation warnings left.
    assert "deprecat" not in result.stderr.lower(), result.stderr
