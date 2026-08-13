# QuantCheck paper publication package

This companion makes the canonical manuscript easy to review and reuse. The
source of truth is [QUANTCHECK_RESEARCH_PAPER.md](QUANTCHECK_RESEARCH_PAPER.md);
the following items must remain consistent with it.

## Updated abstract

Point-in-time financial research can be distorted when a dataset exposes a fact
before it was available, changes a value's scale without changing its unit,
duplicates an occurrence, or substitutes a later revision into an earlier
historical state. QuantCheck is a deterministic Python framework for creating
these four narrow controlled faults, auditing a sanitized manifest-blind input,
and exactly scoring findings against private truth only after detection is
finalized. Its primary controlled evidence is a frozen v0.1 held-out benchmark:
124 configured cases on reviewed synthetic fixtures: 120 fault cases and four
clean controls. Ninety fault cases succeeded, 30 were retained as structurally
ineligible, and all four controls succeeded, for 94 successful cases total.
Across successful cases, 130 injected faults produced 208 findings, with strict primary-family
precision 0.625, recall 1, and 78 retained cross-detector false positives. This
is a controlled contract result, not a real-world performance estimate.

Two real-source evidence layers were evaluated separately. An observational SEC
Company Facts run processed 472 selected observations—180 Assets and 292
NetIncomeLoss—from five issuers. It demonstrated pipeline execution and an
exact-duplicate null result, but Look-Ahead, Revision Overwrite, and Unit Drift
were not applicable under the selected adapter semantics. A distinct
Git-frozen adversarial study then preserved the SEC-derived values and
provenance while using existing injectors. Across nine cases, Look-Ahead,
Duplicate, and Unit Drift exactly matched all 120 injected fault instances;
Unit Drift also emitted four strict false positives, giving Unit Drift micro
precision 0.9 and recall 1. The 120 faults were manufactured test conditions,
not naturally occurring SEC defects. Revision Overwrite remained inapplicable
because the adapter did not declare revision lineage. The evidence supports
specified controlled contracts and real-source pipeline execution, not natural
error prevalence, vendor-scale accuracy, or production readiness.

## One-paragraph nontechnical summary

QuantCheck checks whether historical financial research data could have become
misleading because information appeared too early, a number was scaled
incorrectly, a fact was duplicated, or a later revision replaced an earlier
version. Its main test evidence uses controlled synthetic examples. A small
public SEC data run showed that the pipeline works on real source records, but
only the duplicate check had suitable natural opportunities. A separate
pre-frozen test then inserted controlled errors into selected SEC-derived
observations: it found all 120 inserted errors across three supported checks,
and also kept four extra Unit Drift warnings visible. Those results are not
claims that SEC data contained 120 errors, that every kind of issue was tested
on real data, or that the system is ready for production use.

## Portfolio-paper summary

QuantCheck is a deterministic audit framework for testing point-in-time
financial research data against four narrow failure modes: timestamp leakage,
unit-scale corruption, exact duplicates, and revision overwrite. Its frozen
synthetic benchmark retains both successful detections and structural
ineligibility failures. A 472-observation SEC Company Facts integration study
demonstrated real-source pipeline execution but only an applicable
exact-duplicate null result. In a separately Git-frozen adversarial study on
the same SEC-derived substrate, existing Look-Ahead, Duplicate, and Unit Drift
workflows exactly matched all 120 injected faults across nine cases; four extra
Unit Drift warnings were retained as strict false positives. The work does not
claim natural SEC defect discovery, vendor-scale accuracy, trading performance,
or production readiness.

## Final recommended figures and tables

No figures are created in this milestone. These are specifications for a later
visual-system milestone, using only the paper's frozen values.

| ID | Item | Required content | Guardrail |
| --- | --- | --- | --- |
| F1 | Architecture | Private manifest vs sanitized detector boundary and post-finalization scoring | Never show detector access to private truth. |
| F2 | Look-Ahead timeline | Period end, research cutoff, filing/availability, and controlled early availability | Label as a controlled example. |
| F3 | Controlled benchmark | By-family strict precision, recall, denominator, and no-target cases | Keep structural ineligibility separate from zero performance. |
| F4 | Failure analysis | Retained 30 no-target cells and 78 cross-detector strict false positives | Do not suppress warnings or call all false positives malfunctions. |
| F5 | Evidence taxonomy | Synthetic benchmark, observational SEC run, adversarial SEC-derived study | State “120 injected, not natural SEC faults.” |
| T1 | Observational applicability | Exact Duplicate applicable; other three N/A | Never use 472 as a common detector denominator. |
| T2 | Adversarial results | 120 exact matches, four Unit Drift strict false positives, Revision N/A | Do not aggregate N/A as a zero score. |

## Claim-verification checklist

| Claim | Evidence | Status |
| --- | --- | --- |
| Four v0.1 fault slices are narrow, deterministic, and manifest blind | Ledger A-01, A-07–A-10, B-01–B-04 | Verified |
| v0.1 held-out benchmark has 124 configured cases | Ledger C-01; final benchmark results | Verified |
| v0.1 result is 94 successful, 30 failed, 0 incomplete; 130 faults, 208 findings, precision 0.625, recall 1 | Ledger C-03–C-10 | Verified |
| The 30 failed v0.1 cases are structural no-target injections | Ledger C-13; final benchmark failure analysis | Verified |
| Research-output sensitivity is controlled, not investment performance | Ledger C-11–C-12; methodology | Verified |
| Observational SEC cohort is 472 observations: 180 Assets and 292 NetIncomeLoss from five issuers | Observational results | Verified |
| Observational Exact Duplicate had 472 singleton groups and zero findings | Observational results; applicability artifact | Verified |
| Observational Look-Ahead, Revision Overwrite, and Unit Drift are N/A | Observational results; limitations | Verified |
| Observational pre-execution freeze is not independently publication-verifiable | Observational protocol; limitations | Verified |
| Adversarial protocol precedes outcomes at commit 2150583111dc58a39a15a5584f1ee68fd56ecc66 | Adversarial protocol; run record | Verified |
| Adversarial study has 120 injected faults and 120 exact matches | Adversarial results; run record | Verified |
| Unit Drift has four strict false positives, micro precision 0.9, recall 1 | Adversarial results; adjudication | Verified |
| The four extra warnings are retained and reviewed as injection-correlated | Adversarial results; adjudication | Verified |
| Revision Overwrite was not evaluated on real SEC-derived substrate | Adversarial protocol and results | Verified |
| QuantCheck is not production ready | Ledger A-02 and G; manuscript limitations | Verified |

## Prohibited claims

Do not state or imply any of the following:

1. QuantCheck found 120 natural SEC faults.
2. All four detectors were validated on naturally occurring SEC data.
3. Every detector meaningfully evaluated all 472 SEC observations.
4. Unit Drift had zero false positives in the adversarial study.
5. Revision Overwrite was validated on the SEC-derived substrate.
6. The observational SEC study was formally preregistered or independently
   frozen before execution.
7. Synthetic or real-substrate injected results establish general production,
   vendor-scale, or real-world accuracy.
8. Controlled research-output sensitivity is investment performance, alpha,
   Sharpe, return, or financial-loss evidence.
9. Manifest-assisted replay is detector-only or automatic remediation.
10. QuantCheck is production ready, customer validated, or a complete SEC
    ingestion and statement-reconstruction system.

## Publication-readiness assessment

**PASS for factual manuscript readiness.** A complete canonical manuscript now
exists; significant numerical claims link to retained artifacts; the three
evidence classes are separate; N/A is not represented as zero performance; the
120 injected faults are not presented as natural SEC defects; all four Unit
Drift strict false positives remain reported; and Revision Overwrite's
real-substrate inapplicability is explicit.

**Scope caveat:** this is readiness for a factual research-style manuscript and
the next visual-design milestone, not peer-review acceptance, production
readiness, or a claim of external replication.
