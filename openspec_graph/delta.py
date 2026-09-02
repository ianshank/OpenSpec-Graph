"""Delta lint: which specs went stale *because the machinery moved* (CP-5).

The question this answers is not "is this citation broken" — `validate`
already answers that, with G004 for a missing make target and G005/G008 for a
missing invariant or ADR. It is "which specs still describe the world as it
was", attributed to a change in the repository's own machinery since a saved
baseline. You changed the coverage floor; here are the specs that still cite
the old number.

That attribution is the whole difference, and it cuts both ways: a citation
that was already broken in the baseline is **not** a delta. Reporting it here
would make this verb a second, worse `validate` — the same findings with a
different name, and a reader who cannot tell which of them their last commit
caused.

Pure and stdlib-only, like ``ledger.py`` and ``dialect_card.py``: no file I/O
and no subprocess. The CLI layer reads the baseline card and parses the specs;
this module only compares. That is also what keeps the subprocess boundary
intact — see ``DEC-DL-001`` on why the baseline is a saved dialect card rather
than a git ref.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from . import detect
from .detect import StackProfile
from .parse import ParsedSpec, threshold_values

__all__ = ["DELTA_SCHEMA_VERSION", "DeltaEntry", "build_delta"]

# Version of the `delta --format json` envelope, declared here beside the
# entry whose serialization it describes -- the same pattern as
# dialect_card.SCHEMA_VERSION, witness.WITNESS_SCHEMA_VERSION and
# rule_types.FINDINGS_SCHEMA_VERSION. Every machine-readable output this
# tool emits announces its shape the same way.
DELTA_SCHEMA_VERSION = 1

# The kinds of staleness this verb reports. Named rather than inlined as
# string literals at each construction site, so the JSON contract's vocabulary
# is enumerable in one place and a consumer can switch on it.
KIND_MAKE_TARGET = "make_target"
KIND_INVARIANT = "invariant"
KIND_ADR = "adr"
KIND_THRESHOLD = "threshold"


@dataclasses.dataclass(frozen=True)
class DeltaEntry:
    """One spec citation that the machinery moved out from under.

    Deliberately not a ``rules.Finding``: this is not a rule evaluation. A
    Finding would leak into `rules --json`, `validate`'s counts and the graph's
    ``broken_links``, none of which this verb participates in (``C-DL-2``).
    """

    kind: str
    path: str
    subject: str
    was: str
    now: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "path": self.path,
            "subject": self.subject,
            "was": self.was,
            "now": self.now,
            "detail": self.detail,
        }

    def render(self) -> str:
        return f"{self.kind:12s} {self.path}: {self.detail}"


def _card_list(card: dict[str, object], field: str) -> list[str] | None:
    """A list-valued card field, or ``None`` when the card never carried it.

    ``None`` and ``[]`` mean different things and must not be conflated. A
    card saved before a field existed never tracked that dimension, so
    comparing against it would report every tool upgrade as repository drift —
    the same schema-addition trap ``dialect_card.diff_cards`` documents and
    skips. An absent field disables its whole comparison rather than
    contributing a spurious "everything was removed".
    """
    if field not in card:
        return None
    value = card.get(field)
    if not isinstance(value, list):
        return None
    return [str(item) for item in value]


def _baseline_threshold(card: dict[str, object]) -> int | None:
    """The baseline's coverage floor, or ``None`` if it had none recorded."""
    threshold = card.get("threshold")
    if not isinstance(threshold, dict):
        return None
    value = threshold.get("value")
    return value if isinstance(value, int) else None


def build_delta(
    baseline: dict[str, object],
    profile: StackProfile,
    specs: Sequence[ParsedSpec],
    root: Path | None = None,
) -> list[DeltaEntry]:
    """Every citation that the baseline supported and the live repo no longer does.

    Each check has the same shape, and the shape is the point: the cited thing
    must have been present in ``baseline`` **and** absent (or changed) now.
    Requiring presence in the baseline is what excludes citations that were
    already broken before this comparison began.

    Stable order: path, then kind, then subject — so the JSON output is
    byte-identical across runs on an unchanged pair of inputs.
    """
    baseline_targets = _card_list(baseline, "make_targets")
    baseline_invariants = _card_list(baseline, "invariant_ids")
    baseline_adrs = _card_list(baseline, "adr_ids")
    baseline_floor = _baseline_threshold(baseline)

    live_targets = set(profile.make_targets)
    live_invariants = set(profile.invariant_ids)
    live_adrs = set(profile.adr_ids)
    live_floor = profile.threshold.value if profile.threshold else None

    entries: list[DeltaEntry] = []
    for spec in specs:
        rel = detect.to_posix_relative(spec.path, root)

        if baseline_targets is not None:
            known = set(baseline_targets)
            for target in spec.make_refs:
                if target in known and target not in live_targets:
                    entries.append(
                        DeltaEntry(
                            kind=KIND_MAKE_TARGET,
                            path=rel,
                            subject=target,
                            was="present",
                            now="removed",
                            detail=(
                                f"cites `make {target}`, which existed at the baseline "
                                f"and is no longer a target in this repository"
                            ),
                        )
                    )

        if baseline_invariants is not None:
            known = set(baseline_invariants)
            for inv in spec.invariant_refs:
                if inv in known and inv not in live_invariants:
                    entries.append(
                        DeltaEntry(
                            kind=KIND_INVARIANT,
                            path=rel,
                            subject=inv,
                            was="declared",
                            now="removed",
                            detail=(
                                f"cites {inv}, which was declared at the baseline and is "
                                f"no longer declared in {profile.invariant_source_name}"
                            ),
                        )
                    )

        if baseline_adrs is not None:
            known = set(baseline_adrs)
            for adr in spec.adr_refs:
                if adr in known and adr not in live_adrs:
                    entries.append(
                        DeltaEntry(
                            kind=KIND_ADR,
                            path=rel,
                            subject=adr,
                            was="declared",
                            now="removed",
                            detail=(
                                f"cites {adr}, which was declared at the baseline and is "
                                f"no longer declared in {profile.adr_source_name}"
                            ),
                        )
                    )

        # The headline case. A spec that hard-codes the number the floor used
        # to be is not merely citing a threshold -- it is asserting a value
        # the repository has since changed, and it will keep passing every
        # gate while saying something false.
        if baseline_floor is not None and live_floor is not None and baseline_floor != live_floor:
            for literal in spec.hard_coded_thresholds:
                if _mentions_value(literal, baseline_floor):
                    entries.append(
                        DeltaEntry(
                            kind=KIND_THRESHOLD,
                            path=rel,
                            subject=str(baseline_floor),
                            was=str(baseline_floor),
                            now=str(live_floor),
                            detail=(
                                f"still cites the old coverage floor {baseline_floor}; "
                                f"the detected floor is now {live_floor}"
                            ),
                        )
                    )

    entries.sort(key=lambda e: (e.path, e.kind, e.subject))
    return entries


def _mentions_value(literal: str, value: int) -> bool:
    """Whether a spec line states ``value`` as its single threshold.

    Delegates to ``parse_semantics.threshold_values`` — the same helper G003
    uses — rather than scanning the line here. Two implementations of "what
    counts as a threshold on this line" would eventually disagree, and the
    first version of this function already did: it matched a line reading
    "coverage moved from 80% to 90%" against *both* 80 and 90, while G003
    correctly suppresses a line carrying two threshold-shaped values because
    it cannot tell which one is the claim.

    Requiring exactly one value inherits that judgement instead of
    re-deriving it. A line that names two numbers is describing a change, not
    asserting a floor, and reporting it would be a false positive in the one
    report this verb exists to make trustworthy.
    """
    return threshold_values(literal) == (value,)
