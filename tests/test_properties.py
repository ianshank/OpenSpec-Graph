"""Property-based tests over the parsers (CP-PT).

Coverage floors prove the tests *execute* a line; a property proves something
is true of the line for inputs nobody thought to write down. The four parsers
here are the ones that read untrusted text out of a repository planlint does
not own, which is exactly where hand-picked examples run out: the BOM defect
this suite now guards was found by a probe, not by any of the 700+ example
tests that already existed.

Every property below states an invariant the code already claims, in its
docstring or its design:

* ``parse_makefile`` is deterministic and returns sorted, deduplicated targets
  (``MakefileFacts`` builds them as ``tuple(sorted(set(...)))``).
* ``parse_makefile`` never raises on arbitrary text -- it reads untrusted
  Makefiles, so "does not crash" is a contract, not an aspiration.
* ``strip_define_blocks`` is idempotent -- it blanks a block's lines, so a
  second pass has nothing left to find.
* The upstream parser recognises exactly the requirement headings present,
  independent of heading depth (the drift U005 exists to *report* must not
  change the count U002 works from).
* ``Criterion.is_negative`` depends on wording, not on ASCII casing or
  surrounding whitespace -- every negation pattern is compiled with
  ``re.IGNORECASE``. (ASCII deliberately: a few Unicode letters case-map to
  more than one code point, which is Python's business, not the matcher's.)

``derandomize=True`` is deliberate. This is a merge gate, and a gate that
fails on one run in fifty gets overridden and then deleted; a fixed example
set makes a failure reproducible from the failure message alone. Fixed per
interpreter, strictly: ``st.text()`` samples from the running Python's own
Unicode tables, so 3.10 and 3.13 draw different characters -- each version
is reproducible with itself, which is what a gate needs. It trades
ongoing exploration for that, so widening the search is an explicit local
activity rather than a surprise in CI:

    pytest tests/test_properties.py --hypothesis-seed=random

A counterexample found that way should be added to the example suite as a
named regression test, the way the four documented linter faults were.
"""

from __future__ import annotations

import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from openspec_graph.machinery import parse_makefile, strip_define_blocks
from openspec_graph.parse_model import Criterion
from openspec_graph.parse_upstream import parse_upstream

PROPERTY_SETTINGS = settings(
    max_examples=300,
    derandomize=True,
    # The parsers are pure and fast, but a shared CI runner is not: a
    # per-example deadline would make this a latency test of the runner.
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

# Text that looks like a Makefile often enough to reach the interesting
# branches, mixed with arbitrary unicode so the "never raises" claim is tested
# against input no Makefile would contain. The odd members are deliberate:
# U+FEFF (the BOM defect), NUL, and the line separators Python's splitlines()
# honours but GNU Make does not.
_MAKEISH = st.lists(
    st.sampled_from(
        list(string.ascii_letters + string.digits)
        + list(" \t:=$()%.#-_\n")
        + ["define", "endef", "include ", "ifeq", "endif", "else", ".PHONY", "\r\n", "﻿", "\x00"]
    ),
    max_size=200,
).map("".join)
_ANY_UNICODE = st.text(max_size=400)
_TEXT = st.one_of(
    _MAKEISH,
    _ANY_UNICODE,
    st.tuples(_MAKEISH, _ANY_UNICODE).map(lambda pair: pair[0] + pair[1]),
)


# --- machinery.parse_makefile ----------------------------------------------


@PROPERTY_SETTINGS
@given(_TEXT)
def test_parse_makefile_is_deterministic_with_sorted_unique_targets(text: str) -> None:
    """Same text in, same facts out -- and targets always ordered and unique.

    The dialect card's byte-stability promise (AC-DC-1) rests on this: a set
    iteration leaking into the output would make `detect --diff` report drift
    on an unchanged repository.
    """
    first = parse_makefile(text)
    assert first == parse_makefile(text)
    assert list(first.targets) == sorted(first.targets)
    assert len(set(first.targets)) == len(first.targets)


@PROPERTY_SETTINGS
@given(
    st.text(max_size=400),
    st.sampled_from(["", "﻿", "\x00", "\r\n", "\r", "\n\r"]),
    st.sampled_from(["", "﻿", "\x00", "\r\n", "\r", "\x1c", " ", "\x85"]),
)
def test_parse_makefile_never_raises_on_arbitrary_text(
    text: str, prefix: str, separator: str
) -> None:
    """Reading a stranger's Makefile must not be able to crash the CLI.

    ``detect`` is documented as always safe to point at an unfamiliar clone,
    which makes total-ness part of the contract rather than a nicety.
    """
    payload = prefix + text.replace("\n", separator if separator else "\n")
    facts = parse_makefile(payload)
    assert isinstance(facts.targets, tuple)
    assert facts.confidence in ("low", "high")


@PROPERTY_SETTINGS
@given(_TEXT)
def test_strip_define_blocks_is_idempotent(text: str) -> None:
    """Blanking a define block leaves nothing for a second pass to blank."""
    once, _had_define = strip_define_blocks(text)
    twice, had_define_again = strip_define_blocks(once)
    assert twice == once
    assert had_define_again is False


# --- the upstream parser ----------------------------------------------------

_TITLE_ALPHABET = string.ascii_letters + string.digits + " ,.'()/-"
_title = st.text(alphabet=_TITLE_ALPHABET, min_size=1, max_size=40).filter(
    lambda s: s.strip() and s.strip() == s
)
# Filler headings must not themselves parse as requirement headings, or the
# generator would be disagreeing with the oracle rather than testing it.
_filler_title = _title.filter(lambda s: not s.lower().startswith(("requirement", "req")))
_prose = st.text(alphabet=_TITLE_ALPHABET, max_size=60).filter(
    lambda s: not s.lstrip().startswith("#")
)


@st.composite
def _upstream_spec(draw: st.DrawFn) -> tuple[str, int]:
    """An upstream-dialect delta plus the number of requirements it declares."""
    lines: list[str] = ["# Spec delta - generated", "", "## ADDED Requirements", ""]
    declared = 0
    for _ in range(draw(st.integers(0, 12))):
        kind = draw(st.sampled_from(["req", "req", "filler", "scenario", "prose", "gwt"]))
        if kind == "req":
            depth = draw(st.integers(2, 4))
            separator = draw(st.sampled_from([":", "—", "-"]))
            keyword = draw(
                st.sampled_from(["Requirement", "REQUIREMENT", "requirement", "REQ 1", "REQ7"])
            )
            lines.append(f"{'#' * depth} {keyword}{separator} {draw(_title)}")
            declared += 1
        elif kind == "filler":
            lines.append(f"{'#' * draw(st.integers(2, 4))} {draw(_filler_title)}")
        elif kind == "scenario":
            lines.append(f"{'#' * draw(st.integers(3, 5))} Scenario: {draw(_title)}")
        elif kind == "gwt":
            lines.extend(
                [
                    "- **GIVEN** " + draw(_prose),
                    "- **WHEN** " + draw(_prose),
                    "- **THEN** " + draw(_prose),
                ]
            )
        else:
            lines.append(draw(_prose))
        lines.append("")
    return "\n".join(lines) + "\n", declared


@PROPERTY_SETTINGS
@given(_upstream_spec())
def test_upstream_requirement_count_is_independent_of_heading_depth(
    generated: tuple[str, int],
) -> None:
    """Heading drift is reported (U005), never silently miscounted.

    U002 asks whether every requirement has a scenario, so a requirement the
    parser fails to see is a requirement nothing can report as unverified --
    the same class of silent under-count as the U004 body-blind defect.
    """
    text, declared = generated
    requirements, _criteria = parse_upstream(text)
    assert len(requirements) == declared, text


# --- the negation matcher ---------------------------------------------------

_negation_words = st.lists(
    st.sampled_from(
        list(string.ascii_letters)
        + [" "] * 4
        + ["-", "'", "."]
        + [
            "not", "no", "never", "fail", "block", "is", "are", "zero",
            "deny", "refuse", "reject", "opens", "egress", "aborts", "exit",
        ]
    ),
    max_size=40,
).map("".join)
# Printable ASCII only for the casing property: the invariant is about the
# regexes, not about Unicode. U+0130 (İ) lowercases to two code points and
# breaks `\bis\s+not` under `.lower()` -- a real Python behaviour, not a
# matcher defect, and not something G002 can or should promise about.
_criterion_text = st.one_of(
    _negation_words, st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=80)
)
# Escaped rather than literal: U+00A0 (no-break space) and U+2009 (thin space)
# are indistinguishable from a plain space in source, and both are `isspace()`
# so a criterion really can arrive padded with them.
_whitespace = st.text(
    alphabet=st.sampled_from([" ", "\t", "\n", "\r", "\xa0", "\u2009", "\x0b", "\x0c"]),
    max_size=4,
)


def _case_variant(text: str, mode: int) -> str:
    return (text.upper(), text.lower(), text.swapcase(), text.title(), text.casefold())[mode]


@PROPERTY_SETTINGS
@given(_criterion_text, _criterion_text, st.integers(0, 4), _whitespace, _whitespace)
def test_is_negative_depends_on_wording_not_casing_or_padding(
    text: str, note: str, mode: int, lead: str, trail: str
) -> None:
    """G002 must not turn on how a criterion happens to be capitalised.

    Every negation pattern is compiled ``re.IGNORECASE``, so this is a stated
    invariant. It also guards the tiering work: a future pattern added without
    the flag would fail here rather than in somebody's repository.
    """
    baseline = Criterion(ident="X", text=text, note=note).is_negative
    recased = Criterion(
        ident="X", text=_case_variant(text, mode), note=_case_variant(note, mode)
    ).is_negative
    assert recased == baseline, (text, note, mode)
    padded = Criterion(ident="X", text=lead + text + trail, note=note).is_negative
    assert padded == baseline, (text, note, lead, trail)


# --- the suite's own contract -----------------------------------------------


def test_property_settings_are_derandomized_and_nothing_is_xfailed() -> None:
    """A gate that fails one run in fifty gets overridden and then deleted.

    Every property runs under ``PROPERTY_SETTINGS`` with ``derandomize=True``
    so a failure reproduces from its message, and none is marked ``xfail`` --
    a found counterexample becomes a named regression test instead.
    """
    import inspect
    import sys

    assert PROPERTY_SETTINGS.derandomize is True
    module = sys.modules[__name__]
    properties = [
        fn for name, fn in vars(module).items()
        if name.startswith("test_") and hasattr(fn, "hypothesis")
    ]
    assert len(properties) >= 5, "the five stated properties must all be present"
    for fn in properties:
        marks = getattr(fn, "pytestmark", [])
        assert not any(m.name == "xfail" for m in marks), f"{fn.__name__} is xfail-marked"
    # Each property is decorated with the shared settings object, by name, on
    # its own line -- counted line-anchored so this test's own source cannot
    # inflate the tally.
    import re

    decorated = re.findall(r"^@PROPERTY_SETTINGS$", inspect.getsource(module), re.MULTILINE)
    assert len(decorated) == len(properties), (
        "every property must carry the shared, derandomised settings"
    )

