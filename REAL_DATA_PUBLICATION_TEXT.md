# Corrected publication text for Milestone 3R

This file provides replacement language for the research paper, README, and
portfolio. No research-paper source file was present in the repository, so the
passages below are publication-ready corrections rather than edits to an
unavailable manuscript artifact.

## Abstract replacement

QuantCheck was evaluated at three distinct evidence levels. First, its frozen
synthetic benchmark tested controlled fault contracts. Second, a narrow
observational integration run ingested 472 selected SEC Company Facts records
from five issuers and executed all four detectors. That run supplied an
applicable null result only for exact duplicates: Look-Ahead and Revision
Overwrite were structurally inapplicable under filing-equals-availability
semantics, and Unit Drift had no exact comparable observations. Third, a
prospectively Git-frozen adversarial study retained the real SEC values and
provenance while applying existing deterministic injectors. Across nine seeded
Look-Ahead, Duplicate, and Unit Drift cases, QuantCheck exactly matched all 120
injected fault instances and emitted four additional Unit Drift warnings,
yielding family-level Unit Drift precision 0.9 and recall 1. Revision Overwrite
was not applicable. These results demonstrate real-source pipeline execution
and successful frozen adversarial cases on real-data substrate, not natural SEC
defect prevalence or general real-world accuracy.

## Methodology replacement

The observational study selected Apple, Microsoft, Alphabet, Amazon, and
JPMorgan; USD `Assets` and `NetIncomeLoss`; 10-K/10-Q filings dated 2021-2024;
and a 2024-12-31 audit cutoff. Existing SEC normalization, sanitization, and
detector execution were used without threshold changes. Applicability was
computed separately for each detector.

The follow-up study was frozen in Git before injected outcomes were generated.
It reused the 472 exact accepted SEC observations offline. Look-Ahead and
Duplicate used the complete substrate. For Unit Drift, a predeclared rule kept
one unchanged latest occurrence at equal-value repeated chronology coordinates
and excluded conflicting-value coordinates rather than infer revisions,
yielding 263 records and 239 comparable observations. Existing medium-severity
injectors ran at seeds 101, 202, and 303; detectors received only sanitized
corrupted snapshots; and exact scoring accessed private manifests only after
audit reports were finalized. One clean control was run per applicable family.

## Results replacement

The observational run accepted 472 records: 180 `Assets` and 292
`NetIncomeLoss`. All four detector executions completed and emitted zero
findings. Detector-specific opportunity counts were 0 for Look-Ahead, 0 for
Revision Overwrite, 0 for Unit Drift, and 472 singleton fingerprint groups for
Exact Duplicate, with no duplicate groups of size greater than one.

In the adversarial follow-up, the clean controls emitted zero findings.
Look-Ahead exactly matched 12 of 12 injected faults with no additional
findings. Duplicate exactly matched 72 of 72 with no additional findings. Unit
Drift exactly matched 36 of 36 and emitted four unmatched warnings, for
family-level micro precision 0.9, recall 1, and F1
0.94736842105263157894736842105263157894736842105263. Human review linked all
four warnings to non-target observations neighboring injected targets; they
remain strict false positives in the reported score.

## Real-data subsection replacement

The evidence must be read in layers. The observational study establishes that
the real-source pipeline processed the selected SEC histories and that no exact
duplicate group appeared. It does not meaningfully validate the other three
detectors because their frozen prerequisites were absent. The adversarial study
then asks a different question: whether existing QuantCheck fault slices work
when clean values and provenance come from real SEC observations. Its positive
matches are injected-fault results, not discoveries of natural SEC errors.

## Limitations replacement

The issuer and concept sample is narrow and purposive. The SEC adapter uses
day-level filing-equals-availability semantics and does not declare revision
lineage, leaving Revision Overwrite inapplicable. Unit Drift required a frozen
selection step because repeated chronology coordinates invalidate its exact
series contract. The three seeded cases per family reuse the same substrate and
are not independent. The observational protocol was locally created before
payload inspection but was neither committed nor independently timestamped;
only the later adversarial protocol has a verifiable Git freeze. Neither study
estimates natural-error prevalence, production performance, or general
accuracy across companies, concepts, severities, and data vendors.

## Conclusion replacement

QuantCheck completed a narrow real-source SEC integration and, in a separately
frozen adversarial study, exercised three existing detector families on real
financial observations without modifying detector logic. The observational
run supports an exact-duplicate null result and pipeline execution only. The
adversarial run matched all 120 injected fault instances while retaining four
additional Unit Drift warnings. Revision Overwrite remains unvalidated on this
substrate. The evidence is encouraging for the specified contracts but is not
broad real-world validation.

## Table and caption corrections

- **Observational table caption:** “Detector-specific applicability and output
  on 472 selected SEC Company Facts records. The 472 records are not a common
  detector denominator; three families had zero eligible opportunities.”
- **Adversarial table caption:** “Exact hidden-manifest scoring for nine
  prospectively frozen injected cases on real SEC observation substrate.
  Faults are manufactured test conditions, not natural SEC defects.”
- **Unit Drift note:** “Four unmatched warnings remain strict false positives;
  human review identified them as correlated alerts on non-target neighbors of
  injected observations.”

## Portfolio abstract

QuantCheck was tested beyond synthetic fixtures using five pinned SEC Company
Facts histories. A 472-record observational run verified real-source ingestion
but exposed an important limitation: only the exact-duplicate detector had
applicable natural opportunities. A separately Git-frozen adversarial study
then preserved the real SEC values and provenance while applying QuantCheck's
existing deterministic fault injectors. Across nine Look-Ahead, Duplicate, and
Unit Drift cases, all 120 injected fault instances were detected; four
additional Unit Drift warnings were retained as false positives. Revision
Overwrite was not applicable. No detector thresholds or logic were changed.

## Concise public summary

QuantCheck processed 472 selected SEC Company Facts observations from five
issuers. The observational run demonstrated real-source pipeline execution but
broadly validated only the exact-duplicate null result; three other detector
families lacked eligible opportunities. In a separately frozen adversarial
study on the same real-data substrate, existing Look-Ahead, Duplicate, and Unit
Drift workflows matched all 120 injected fault instances across nine cases and
retained four additional Unit Drift warnings. These are controlled
real-substrate results, not discoveries of natural SEC defects or general
real-world accuracy.
