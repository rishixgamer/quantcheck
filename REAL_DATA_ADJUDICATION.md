# Real-public-data observational adjudication

## Finding-level table

The run emitted zero findings, so there are no classifications. This empty
table is not evidence that the accepted facts were correct.

| Finding ID | Company / CIK | Detector rule | Category | Detector-established evidence | Human-review evidence and rationale | Source SHA-256 | Review date | Uncertainty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _No emitted findings_ | — | — | — | — | — | — | — | — |

`REAL_DATA_FINDINGS.csv` remains header-only and preserves the complete finding
output.

## Category accounting

| Predeclared category | Finding count |
| --- | ---: |
| likely genuine issue | 0 |
| legitimate revision/history behavior | 0 |
| legitimate unusual observation | 0 |
| correlated/redundant warning | 0 |
| known detector limitation | 0 |
| false or low-value alert | 0 |
| ambiguous / cannot determine | 0 |
| **Total classified findings** | **0** |

## Applicability review is not adjudication

The retrospective applicability audit classifies detector opportunities, not
findings:

| Detector | Opportunity count | Review conclusion |
| --- | ---: | --- |
| Look-Ahead Timestamp | 0 | NOT_APPLICABLE under `available_on == filed_on`. |
| Revision Overwrite | 0 | NOT_APPLICABLE without a detector-visible early-availability/later-filing relationship or declared adapter lineage. |
| Unit Drift | 0 | NOT_APPLICABLE because repeated chronology coordinates exclude every exact comparable series. |
| Exact Duplicate | 472 fingerprint groups | Applicable; all groups were singletons and no finding was emitted. |

## A, B, and C

| Layer | Conclusion |
| --- | --- |
| A. What QuantCheck detected | Zero findings; 472 singleton exact-fingerprint groups; no detector-visible violation from the other families. |
| B. What human review concluded | No finding could be adjudicated. Three detector families lacked applicable opportunities, so their null outputs cannot be treated as validation evidence. |
| C. What remains uncertain | Whether unalerted or excluded facts contain defects, whether source histories encode revisions not declared by the adapter, and how the detectors behave on naturally eligible real histories. |
