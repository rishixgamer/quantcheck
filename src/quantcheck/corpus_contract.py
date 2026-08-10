"""Frozen conventions for the v0.2 benchmark corpus substrate.

The v0.1 benchmark ran on a 26-record reviewed fixture plus a five-observation
Unit Drift series. That produced three structurally ineligible profile/severity
cells and denominators as thin as eleven. This module owns the conventions of
the replacement *data substrate*, whose whole purpose is external validity.

It owns no scientific rule. Fault eligibility, detector thresholds, matching,
replay, and research behaviour stay exactly where v0.1 froze them, in the four
completed fault families; the corpus only supplies clean sources and *counts*
how many units each frozen rule finds eligible.

Three deliberate boundaries live here:

**Source class.** A corpus unit is one of exactly three kinds — a deterministic
synthetic adversarial cohort, a curated public financial-data document, or an
externally supplied private/vendor dataset. Only the first two may live in the
repository; the third is never required for any ordinary test or gate.

**Partition.** Every unit belongs to exactly one of ``development``,
``validation``, or ``heldout``, declared in the source definition before any
detector is run against it. The held-out partition is separately frozen and its
records cannot be materialized without an explicit authorization, mirroring the
final-seed rule ADR-010 froze for v0.1: the gate is about *execution*, not
representation.

**Leakage.** A partition label is corpus metadata. It must not appear in any
field a manifest-blind detector can see, so unit-level detector-visible naming
(``source_name``, ``source_locator``, ``audit_dataset_name``) is required to be
an opaque cohort code rather than a readable partition name.
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "CORPUS_ELIGIBILITY_UNIT_KINDS",
    "CORPUS_FAULT_PROFILES",
    "CORPUS_INCLUSION_RULES",
    "CORPUS_LICENSE_TIERS",
    "CORPUS_PARTITIONS",
    "CORPUS_SEVERITIES",
    "CORPUS_SOURCE_CLASSES",
    "CORPUS_SPEC_VERSION",
    "CORPUS_UNSUPPORTED_REASON_CODES",
    "HELD_OUT_PARTITION",
    "IN_REPOSITORY_SOURCE_CLASSES",
    "MINIMUM_CELL_ELIGIBLE_UNITS",
    "MINIMUM_PARTITION_ELIGIBLE_UNITS",
    "PARTITION_LEAKAGE_TOKENS",
    "REDISTRIBUTABLE_LICENSE_TIERS",
    "CorpusContractError",
    "corpus_cells",
    "inclusion_rule_description",
]

#: The corpus contract version. Every corpus artifact carries it, and changing
#: it changes every corpus identifier.
CORPUS_SPEC_VERSION: Literal["quantcheck/corpus/v2"] = "quantcheck/corpus/v2"

#: The three source classes, in stable order. This is a closed list: a source
#: that fits none of them is rejected rather than filed under the nearest one.
CORPUS_SOURCE_CLASSES: tuple[str, ...] = (
    "synthetic_adversarial",
    "curated_public",
    "external_private",
)

#: Source classes whose bytes may be committed to this repository. Anything
#: else is referenced by declaration only.
IN_REPOSITORY_SOURCE_CLASSES: tuple[str, ...] = (
    "synthetic_adversarial",
    "curated_public",
)

#: Licensing tiers, in stable order.
#:
#: ``synthetic_repository``
#:     Wholly invented data authored for this repository under its own licence.
#: ``public_government``
#:     Curated from a public government disclosure system (SEC EDGAR Company
#:     Facts). Redistributable, but its provenance must record whether the
#:     bytes are a verbatim saved response.
#: ``external_restricted``
#:     Supplied by a third party under terms this repository does not hold.
#:     Never committed, never required, never quoted in any saved artifact.
CORPUS_LICENSE_TIERS: tuple[str, ...] = (
    "synthetic_repository",
    "public_government",
    "external_restricted",
)

#: Licence tiers whose record content may appear in a committed artifact.
REDISTRIBUTABLE_LICENSE_TIERS: tuple[str, ...] = (
    "synthetic_repository",
    "public_government",
)

#: The three corpus partitions, in stable order.
CORPUS_PARTITIONS: tuple[str, ...] = ("development", "validation", "heldout")

HELD_OUT_PARTITION: Literal["heldout"] = "heldout"

#: Fault profiles the census covers. Duplicated from the frozen v0.1 benchmark
#: contract by value rather than imported, so a future corpus-only profile can
#: be added without reaching into a frozen module.
CORPUS_FAULT_PROFILES: tuple[str, ...] = (
    "duplicate_observation",
    "lookahead_timestamp",
    "revision_overwrite",
    "unit_drift",
)

CORPUS_SEVERITIES: tuple[str, ...] = ("low", "medium", "high")

#: What one eligible unit *is*, per family. These are the frozen v0.1
#: definitions, restated so the census's denominators are unambiguous.
CORPUS_ELIGIBILITY_UNIT_KINDS: dict[str, str] = {
    "lookahead_timestamp": "eligible_clean_record",
    "unit_drift": "comparable_observation",
    "duplicate_observation": "singleton_fingerprint_group",
    "revision_overwrite": "revision_history_unit",
}


def corpus_cells() -> tuple[tuple[str, str], ...]:
    """Every ``(fault_profile, severity)`` cell the corpus must account for."""
    return tuple(
        (profile, severity) for profile in CORPUS_FAULT_PROFILES for severity in CORPUS_SEVERITIES
    )


#: The corpus adequacy floors.
#:
#: These are *corpus* thresholds, not detector thresholds. They say how much
#: clean population a cell needs before a measurement taken in it means
#: anything; they never change what a detector finds. Both numbers are declared
#: here, before any held-out evidence exists, precisely so that they cannot be
#: chosen afterwards to make a cell pass. See ADR-V2-002.
#:
#: ``MINIMUM_CELL_ELIGIBLE_UNITS`` applies to the *best single unit* in a
#: partition, because one benchmark case runs against one clean source: a cell
#: spread thinly over three units is not measurable by any one case. Eight is
#: the smallest count at which the lowest configured target fraction (1% for
#: Duplicate, 2% elsewhere, each with a minimum-one ceiling) still selects a
#: target from a population large enough to leave clean units behind it.
MINIMUM_CELL_ELIGIBLE_UNITS = 8

#: ``MINIMUM_PARTITION_ELIGIBLE_UNITS`` applies to the partition-wide total for
#: a cell, so a false-positive denominator pooled across a partition is not
#: dominated by a single unit.
MINIMUM_PARTITION_ELIGIBLE_UNITS = 24

#: Reason codes a cell may be declared unsupported under. A declaration is the
#: only permitted alternative to eligibility, and it must be made before the
#: held-out freeze.
CORPUS_UNSUPPORTED_REASON_CODES: tuple[str, ...] = (
    "source_class_cannot_express",
    "frozen_threshold_unreachable",
    "deliberately_out_of_scope",
)

#: The documented corpus inclusion rules. A unit records the identifiers of the
#: rules it was admitted under; the census refuses a unit citing an unknown
#: rule. Selection happens against these rules and nothing else — in
#: particular, never against observed detector performance.
CORPUS_INCLUSION_RULES: dict[str, str] = {
    "IR-01": (
        "A unit is admitted for the diversity axis it adds — issuer, fiscal "
        "calendar, period count, concept, filing lag, unit of measure, "
        "revision history, volatility, or hard negative — declared before the "
        "unit is generated."
    ),
    "IR-02": (
        "A unit's partition is declared in its source definition and never "
        "changed afterwards. Reassigning a unit between partitions is a new "
        "corpus with a new identifier, not an edit."
    ),
    "IR-03": (
        "No unit may be added, removed, resized, or re-parameterised on the "
        "basis of observed detector performance on any partition. Corpus "
        "changes are justified by an eligibility or diversity argument only."
    ),
    "IR-04": (
        "Issuer identities are disjoint across partitions. No entity_id, "
        "record_id, or source_locator appears in two partitions."
    ),
    "IR-05": (
        "Detector-visible naming carries no partition information. "
        "source_name, source_locator, and audit_dataset_name are opaque "
        "cohort codes."
    ),
    "IR-06": (
        "Every unit is regenerated by a pure in-package factory from committed "
        "inputs. No unit depends on the clock, randomness, the filesystem "
        "layout, or a network request at generation time."
    ),
    "IR-07": (
        "Hard negatives are natural but unusual legitimate observations, "
        "declared individually with the reason they are legitimate. A hard "
        "negative is never an injected fault."
    ),
    "IR-08": (
        "Licensed customer or vendor data is never committed. An "
        "external_private unit is referenced by declaration only, and no "
        "record content from it may enter any repository artifact."
    ),
    "IR-09": (
        "A curated public unit records whether its bytes are a verbatim saved "
        "response. A curated field-shape excerpt is never described as a "
        "live retrieval."
    ),
}


def inclusion_rule_description(rule_id: str) -> str:
    """Return the documented text of one inclusion rule."""
    try:
        return CORPUS_INCLUSION_RULES[rule_id]
    except KeyError:
        raise CorpusContractError(f"unknown corpus inclusion rule: {rule_id!r}") from None


#: Tokens that must never appear in detector-visible text. The partition names
#: themselves plus the conventional machine-learning synonyms, because a unit
#: named "train" or "holdout" leaks exactly as much as one named "heldout".
PARTITION_LEAKAGE_TOKENS: tuple[str, ...] = (
    "development",
    "validation",
    "heldout",
    "held_out",
    "held-out",
    "holdout",
    "hold_out",
    "hold-out",
    "train",
    "training",
    "valid",
    "test",
    "eval",
)


class CorpusContractError(ValueError):
    """Raised when a corpus input violates a frozen corpus convention."""
