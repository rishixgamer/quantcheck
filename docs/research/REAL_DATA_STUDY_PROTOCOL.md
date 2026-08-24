# QuantCheck real-public-data observational study protocol

## Status and evidentiary timing

This document is the corrected protocol record for the completed observational
SEC Company Facts run. The run itself is preserved unchanged under
`evidence/real_data_study/`; this correction changes its interpretation, not
its inputs, execution, or outputs.

Study protocol file was created before source-payload inspection, but was not
independently timestamped or committed before execution. Therefore this study
should be described as prospectively specified in the local workflow, not as
formally preregistered.

The completed run record retains the SHA-256 of the protocol bytes present at
execution (`f7add2f1c3cd44e2ac24090c516ed43cbed591d868f59e5aff0d4bd544288f6f`).
Because this corrected document is necessarily different, that hash does not
authenticate the present prose. No claim is made that an independent reviewer
could verify the ordering of protocol creation and outcome inspection from the
local files alone.

## Question

> How does QuantCheck behave when exposed to real public financial-data
> histories rather than only the controlled benchmark?

This run addresses real-source ingestion and detector execution on a narrow
cohort. Its detector-specific opportunity audit determines what, if anything,
the zero-finding result says about each detector.

## Fixed sample and input scope

The purposive sample comprised five large US registrants:

| Company | CIK |
| --- | ---: |
| Apple Inc. | 0000320193 |
| Microsoft Corporation | 0000789019 |
| Alphabet Inc. | 0001652044 |
| Amazon.com, Inc. | 0001018724 |
| JPMorgan Chase & Co. | 0000019617 |

The input rules were:

- SEC Company Facts, one exact endpoint response per CIK;
- filing dates from 2021-01-01 through 2024-12-31, inclusive;
- forms `10-K` and `10-Q` only;
- `us-gaap:Assets`, USD, instant; and
- `us-gaap:NetIncomeLoss`, USD, duration;
- end-of-day audit cutoff 2024-12-31; and
- the adapter's source-supported day-level convention
  `available_on == filed_on`.

No extension taxonomy, statement reconstruction, currency conversion, period
harmonization, inferred revision lineage, filing-HTML review, or missing-fact
inference was performed.

## Detector configuration

All four detectors were executed once per issuer through existing
`run_selected_detectors_v2` functionality. The canonical serialized order was:

1. `duplicate_observation`
2. `lookahead_timestamp`
3. `revision_overwrite`
4. `unit_drift`

Look-Ahead, Duplicate Observations, and Revision Overwrite used their existing
no-parameter detector contracts. Unit Drift used the existing defaults:
`ratio_threshold=50` and supported factors `100`, `1000`, and `1000000`.
There was no detector tuning, fault injection, private manifest, scoring,
replay, or research-impact calculation.

## Detector-specific applicability rules

Applicability is not the accepted-record count. It is assessed separately for
each detector using its frozen prerequisites:

- **Look-Ahead:** count records capable of satisfying the detector's
  available-before-filing condition. With `available_on == filed_on`, the
  opportunity count is structurally zero.
- **Revision Overwrite:** count records carrying the detector-visible
  early-availability/later-filing relationship needed by the rule. The adapter
  neither creates that relationship nor declares revision lineage, so the
  opportunity count is zero.
- **Unit Drift:** count observations returned by the existing exact
  `build_comparable_observations` construction. A series with repeated
  chronology coordinates is excluded rather than ordered by guesswork.
- **Duplicate Observations:** count exact detector fingerprint groups and the
  subset with group size greater than one.

The machine-readable retrospective applicability audit is
`../../evidence/real_data_study/applicability.json`.

## Cache-first collection provenance

The runner called the existing cache-first adapter. It did not save the
per-fetch `from_cache` flag, so the original execution cannot now establish
which individual CIK responses were live downloads and which, if any, were
cache reuses. This uncertainty must remain explicit.

What is preserved is exact cache identity: five immutable raw filenames,
their SHA-256 digests, accepted-cache pointers, source URLs, and local file
modification times. The run saved one completion timestamp,
`2026-08-13T16:15:30Z`; it did not save per-request start or completion times.
The preserved cache identities, rather than a later SEC response, define the
source bytes analyzed.

## Exclusions and adjudication

Entries outside the fixed concepts, units, forms, filing dates, or period
shapes were explicit exclusions, not detector negatives. Every emitted finding
would have received exactly one of these frozen review categories:

- likely genuine issue;
- legitimate revision/history behavior;
- legitimate unusual observation;
- correlated/redundant warning;
- known detector limitation;
- false or low-value alert; or
- ambiguous / cannot determine.

No findings were emitted, so no finding-level classification was made. An
absence of findings is not a clean-data certification.

## Reporting boundary

Report accepted records by concept, detector-specific opportunity counts, and
all uncertainty. Do not calculate observational precision, recall, accuracy,
or a common 472-record detector denominator. Do not describe this local freeze
as preregistration. Do not interpret an inapplicable detector's zero output as
a successful negative test.
