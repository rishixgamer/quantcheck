# QuantCheck real-public-data observational results

## Result at a glance

QuantCheck accepted 472 selected SEC Company Facts records from five issuers
and completed five executions of each of its four detector families. The runs
emitted no findings. Detector-specific applicability review materially narrows
that result: only the exact-duplicate rule had a nonzero observational
opportunity denominator.

## Source composition

| Concept | Accepted records | Share of accepted records |
| --- | ---: | ---: |
| `Assets` | 180 | 180 / 472 |
| `NetIncomeLoss` | 292 | 292 / 472 |
| **Total** | **472** | **472 / 472** |

| Company | CIK | Raw-response SHA-256 | Accepted records | Explicit exclusions | Detector execution ID |
| --- | ---: | --- | ---: | ---: | --- |
| Apple Inc. | 0000320193 | `73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43` | 84 | 25,051 | `dexec2_ace75e3c59c8e4e4` |
| Microsoft Corporation | 0000789019 | `f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f` | 84 | 32,587 | `dexec2_5a2fa915818e744a` |
| Alphabet Inc. | 0001652044 | `a017f26ee88cb4a639d1c1ddb06d53b4afe22f0ac89cabec7cd67c88919fe1c5` | 84 | 20,823 | `dexec2_a322a0a87cb18973` |
| Amazon.com, Inc. | 0001018724 | `e6aadb0da7384597dbd78f74d1379ffb7fd0829a4d2e797b6d7e442b5e1da0d7` | 120 | 29,635 | `dexec2_85ab0ec486686b3d` |
| JPMorgan Chase & Co. | 0000019617 | `3b3979043e98dcc2436b553111ef5d61544844c1a4d3bbeeaa3ec8ff5a84f0a2` | 100 | 53,133 | `dexec2_bf2a0056e1671ee4` |
| **Total** | **5 issuers** | **5 pinned responses** | **472** | **161,229** | **5 executions** |

Exclusions are source entries outside the selected concepts, USD unit, forms,
filing dates, or period shapes. They are not detector negatives.

## Detector-specific applicability and findings

| Detector | Applicable opportunity definition | Opportunities | Findings | Interpretation |
| --- | --- | ---: | ---: | --- |
| Look-Ahead Timestamp | Records capable of satisfying available-before-filing under the normalized chronology | 0 | 0 | **NOT_APPLICABLE**: all 472 records have `available_on == filed_on`. |
| Revision Overwrite | Records exposing the rule's early-availability/later-filing relationship | 0 | 0 | **NOT_APPLICABLE**: the adapter declares independent occurrences and supplies no such relationship or inferred revision lineage. |
| Unit Drift | Existing exact comparable observations | 0 | 0 | **NOT_APPLICABLE**: every candidate series has repeated chronology coordinates and is excluded by the frozen comparability contract. |
| Exact Duplicate | Exact detector fingerprint groups | 472 groups | 0 | **Applicable null result**: all 472 groups were singletons; 0 groups had size greater than one. |

The 472 accepted records are therefore not a scientifically valid common
denominator for the four detectors. In particular, there is no basis for
saying Unit Drift candidates were examined and failed the fixed threshold:
there were no eligible comparable observations on which to apply that test.

## A. What QuantCheck detected

All four detector executions completed, and none emitted a finding. The exact
duplicate detector grouped the 472 records into 472 singleton fingerprints.
The other three detectors had zero eligible opportunities under the normalized
input structure.

## B. What human review concluded

There were no findings to classify. Human review established detector-specific
applicability and corrected the original common-denominator interpretation. It
did not certify any issuer fact, SEC history, or excluded source entry.

## C. What remains uncertain

This run cannot estimate sensitivity, precision, false-positive rate, or
accuracy; determine whether any unalerted fact is correct; evaluate natural SEC
revision histories; or generalize beyond the selected issuers, concepts,
period, adapter semantics, and exact cached bytes. The original cache-first run
also did not retain per-request live-versus-cache flags.

## Corrected conclusion

QuantCheck successfully ingested 472 selected SEC Company Facts records from five issuers and completed all four detector executions. The exact-duplicate detector found no duplicate fingerprint groups. Look-Ahead and Revision Overwrite were structurally inapplicable under the adapter's filing-equals-availability semantics, and Unit Drift had no eligible comparable observations. The study therefore demonstrates real-source pipeline execution, not broad real-data detector validation.
