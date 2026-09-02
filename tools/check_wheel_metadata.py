"""Gate: the built wheel actually carries its licence — `AC-LM-3`.

Why this exists as an artifact check rather than a build check. The obvious
fail-closed criterion for the PEP 639 migration was "a build with no LICENSE
file fails". It does not: setuptools accepts a `license-files` glob that
matches nothing and produces a wheel with no licence at all, silently. So the
only honest gate reads the artifact and asserts what it must contain.

Checks, against every wheel in the given directory:

1. ``License-Expression`` is present in METADATA and matches the SPDX
   expression declared in ``pyproject.toml`` — read from the project, never
   restated here, so this script cannot drift from the source of truth.
2. No legacy ``License ::`` classifier survives, which PEP 639 forbids
   alongside an SPDX expression and setuptools>=77 rejects.
3. Every file named by ``license-files`` is present under
   ``.dist-info/licenses/`` and is non-empty.

Exit 0 clean, 1 on a violation, 2 when the check could not run — the same
three-way contract the CLI itself publishes.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_text, repo_root

# The metadata key PEP 639 defines for the SPDX expression, and the legacy
# classifier prefix it replaces. Named rather than inlined so the two places
# below that reference each cannot drift.
_EXPRESSION_KEY = "License-Expression:"
_LEGACY_CLASSIFIER = "Classifier: License ::"
_LICENSE_DIR = "licenses/"


def _declared_license(pyproject: str) -> tuple[str, list[str]]:
    """The SPDX expression and licence-file globs declared in pyproject.

    Deliberately a narrow scan rather than a TOML parse: this repository
    targets Python 3.10, where ``tomllib`` is absent from the stdlib, and the
    project has no runtime dependencies to spend on a backport for one gate
    script (the same reasoning as the existing threshold scanners).
    """
    expression = ""
    files: list[str] = []
    for line in pyproject.splitlines():
        stripped = line.strip()
        if stripped.startswith("license =") and '"' in stripped:
            expression = stripped.split('"')[1]
        elif stripped.startswith("license-files"):
            files = list(stripped.split('"')[1::2])
    return expression, files


def check_wheel(wheel: Path, expression: str, license_files: list[str]) -> list[str]:
    """Every violation in one wheel. Empty list means it passed."""
    problems: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [n for n in names if n.endswith(".dist-info/METADATA")]
        if not metadata_names:
            return [f"{wheel.name}: no .dist-info/METADATA in the wheel"]
        metadata = archive.read(metadata_names[0]).decode("utf-8")

        expected = f"{_EXPRESSION_KEY} {expression}"
        if expected not in metadata:
            problems.append(
                f"{wheel.name}: METADATA is missing {expected!r} "
                f"(pyproject declares license = {expression!r})"
            )
        for line in metadata.splitlines():
            if line.startswith(_LEGACY_CLASSIFIER):
                problems.append(
                    f"{wheel.name}: legacy classifier {line!r} cannot coexist "
                    "with an SPDX License-Expression (PEP 639)"
                )

        for declared in license_files:
            matches = [
                n for n in names if _LICENSE_DIR in n and n.endswith(f"/{Path(declared).name}")
            ]
            if not matches:
                problems.append(
                    f"{wheel.name}: {declared!r} is declared in license-files but no "
                    f"matching file was packaged under .dist-info/{_LICENSE_DIR}"
                )
                continue
            if not archive.read(matches[0]).strip():
                problems.append(f"{wheel.name}: packaged licence {matches[0]!r} is empty")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dist", nargs="?", default="dist", help="directory holding the built wheel(s)"
    )
    args = parser.parse_args(argv)

    dist = Path(args.dist)
    if not dist.is_dir():
        print(f"ERROR not a directory: {dist}", file=sys.stderr)
        return 2

    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        # Exit 2, not 0: "nothing to check" must never read as "everything
        # passed". A release job whose build step silently produced no wheel
        # would otherwise sail through this gate.
        print(f"ERROR no wheels found in {dist}", file=sys.stderr)
        return 2

    expression, license_files = _declared_license(read_text(repo_root() / "pyproject.toml"))
    if not expression:
        print("ERROR pyproject.toml declares no SPDX license expression", file=sys.stderr)
        return 2

    problems = [p for wheel in wheels for p in check_wheel(wheel, expression, license_files)]
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1

    print(
        f"PASS {len(wheels)} wheel(s) carry License-Expression: {expression} "
        f"and {len(license_files)} licence file(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
