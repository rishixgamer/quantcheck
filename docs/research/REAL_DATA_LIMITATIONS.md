# Real-public-data observational study limitations

1. **Three detectors were inapplicable.** Look-Ahead and Revision Overwrite had
   zero eligible opportunities under filing-equals-availability semantics.
   Unit Drift had zero exact comparable observations. Their zero outputs are
   not validation results.
2. **Only Exact Duplicate had a nonzero denominator.** The relevant result is
   0 duplicate groups among 472 exact fingerprint groups, not 0 findings among
   472 records for every detector.
3. **No ground truth.** The observational run had no injected faults or
   independently labelled error corpus. It cannot estimate precision, recall,
   sensitivity, specificity, false-positive rate, or accuracy.
4. **Narrow purposive cohort.** Five large US registrants, two US-GAAP
   concepts, two form types, and 2021-2024 filings are not representative of
   issuers, filings, accounting policies, vendor feeds, or research datasets.
5. **Concept imbalance.** The 472 accepted records comprise 180 `Assets` and
   292 `NetIncomeLoss` records; results are not concept-balanced.
6. **SEC Company Facts scope.** The endpoint is an entity-wide aggregation,
   not filing-HTML reconstruction, a restatement database, or a point-in-time
   vendor history.
7. **No inferred revision lineage.** The adapter treats accepted rows as
   independent source occurrences. Revision relationships cannot be guessed
   from similar facts or accessions.
8. **Exact duplicate scope.** The fingerprint is accession- and
   source-identity-aware. It does not test near duplicates or repeated economic
   facts represented by different source occurrences.
9. **Unit Drift structural collision.** Repeated chronology coordinates cause
   an entire exact comparable series to be excluded. It is unsupported to say
   that eligible candidates failed ratio threshold 50; there were no eligible
   comparable observations.
10. **One historical cutoff.** The 2024-12-31 end-of-day snapshot is not a
    rolling point-in-time evaluation.
11. **Source drift.** Company Facts responses update. Only the saved SHA-256
    identities define the evaluated bytes.
12. **Incomplete retrieval provenance.** The cache-first runner did not retain
    each fetch's `from_cache` flag or per-request completion time. It preserved
    exact accepted-cache pointers and raw digests, plus a single run completion
    timestamp. Live download versus cache reuse for each CIK cannot be
    reconstructed.
13. **Local freeze only.** Study protocol file was created before
    source-payload inspection, but was not independently timestamped or
    committed before execution. Therefore this study should be described as
    prospectively specified in the local workflow, not as formally
    preregistered.
14. **No exhaustive manual audit.** No issuer-level review of all 472 accepted
    records against filings occurred because no finding was emitted.

## Appropriate conclusion

The study demonstrates that QuantCheck's selected SEC ingestion,
normalization, sanitization, and all four detector execution paths completed on
five pinned public-source histories. It supplies a narrow applicable null result
for exact duplicates only. It does not broadly validate the other detectors on
natural real data or certify the source histories.
