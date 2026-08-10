# Design-partner shadow mode

## Purpose and boundary

This workflow supports an actual external design-partner evaluation without claiming that one has
already happened. No pilot number or customer result is checked into this repository.

Shadow mode audits an integrity-pinned **copy or snapshot** of a customer's dataset. The customer's
production research system remains the system of record. QuantCheck does not connect to it, write
to it, repair it, pause it, approve it, reject it, or sit in its execution path. A policy action
named `blocking` is a severity/classification inside the copied audit report only;
`production_blocking_used=false` in every shadow finding bundle.

The workflow reuses, unchanged:

- `DatasetMappingV1` / `quantcheck/dataset-mapping/v1` for explicit customer-column, Decimal,
  period, availability, provenance, and revision semantics;
- `AuditPolicyV1` / `quantcheck/audit-policy/v1` for detector selection, actions, supported
  thresholds, expectations, and pre-approved exceptions;
- `ExternalAuditExecutionPlanV1` and the self-hosted batch runner for content-addressed,
  manifest-free local execution; and
- `ExternalDatasetAuditReportV2` as the immutable public audit evidence.

The shadow layer never accepts source rows, normalized private records, a manifest, an injector,
benchmark truth, or an automatic remediation instruction. It starts only after public audit reports
are finalized.

## Roles and artifact separation

| Artifact | Audience | Contains | Must not contain |
|---|---|---|---|
| Customer mapping and policy | customer data owner and QuantCheck operator | explicit data semantics and reviewed policy | guessed availability/revision semantics |
| Researcher finding bundle | customer research reviewers | exact unchanged findings, evidence, policy context, report hashes, version/code identity | reviewer edits or dispositions inside a finding |
| Adjudication input/export | approved evaluation team | finding ID/hash, detector, investigation state, disposition, independently confirmed decision-impact state, review seconds | finding evidence, customer values/record IDs, reviewer notes |
| Reviewer notes | customer-controlled private storage | free-text notes linked to exact finding hashes | inclusion in pilot metrics or the sanitized export |
| Rerun comparison | customer research reviewers | exact added/removed/changed/unchanged references and audit-context match | fuzzy matches, rewritten evidence, causal claims |
| Pilot report | approved aggregate recipients | source artifact hashes and aggregate counts/times | customer/dataset names, findings, values, notes, customer records |

The sanitized export is privacy-minimized, not anonymous. Stable finding and artifact identifiers
can remain linkable to the customer-held finding bundle. Treat it as sensitive and obtain customer
approval before sharing. Aggregate counts can also be commercially sensitive, especially for a
small pilot.

## Before the first audit

1. Agree a pseudonymous `dataset_key`, pilot purpose, reviewers, access controls, retention period,
   and deletion owner. Do not put a customer name in `dataset_key` or `pilot_key`.
2. Have the customer create a read-only export or filesystem snapshot outside the production
   research path. Record its exact SHA-256 and byte size. Keep production and QuantCheck output/work
   roots separate.
3. Complete and source-owner-review `DatasetMappingV1`. Availability must cite its source contract;
   revision lineage must be source-declared or explicitly absent. Run the validation-only dry run
   first. A dry run is not an audit result.
4. Complete and customer-approve `AuditPolicyV1`. Record detector actions, the exact Unit Drift
   threshold, expectations, and each reasoned exception. Example policies in the repository are
   fictional contract examples, not recommendations.
5. Build the content-addressed execution plan and keep its mapping, policy, source hashes, as-of
   date, partition identities, QuantCheck version, code/image revision, and environment evidence.
6. Define how wall-clock runtime and researcher review seconds will be measured. Runtime passed to
   this package is supplied operational evidence; QuantCheck does not infer it from file dates.

See `docs/EXTERNAL_DATASETS.md`, `docs/PRODUCTION_AUDIT_POLICIES.md`, and
`docs/SELF_HOSTED_DEPLOYMENT.md` for the input, policy, and hardened batch contracts.

## Run without affecting production

Run the self-hosted audit against the mounted snapshot with network disabled and the input mount
read-only. A failed validation, partition, or audit stops only this copied shadow run. It must not be
wired to a production job's success condition.

After the run, verify the public finalization and every public report hash. Measure the audit
runtime with the agreed monotonic process/container wrapper. Then package one logical dataset's
partition reports:

```sh
python -m quantcheck.external_dataset_shadow prepare \
  --audit-report /shadow-output/public/partitions/PARTITION_1/audit_report.json \
  --audit-report /shadow-output/public/partitions/PARTITION_2/audit_report.json \
  --dataset-key dp-dataset-opaque-001 \
  --quantcheck-version VERSION_USED \
  --code-revision EXACT_COMMIT_OR_IMAGE_DIGEST \
  --runtime-ns MEASURED_RUNTIME_NS \
  --execution-run-id CONTENT_ADDRESSED_RUN_ID \
  --execution-finalization-id VERIFIED_FINALIZATION_ID \
  --output-directory /customer-controlled/shadow-review-001
```

`prepare` refuses overwrite and writes:

```text
shadow-review-001/
├── researcher_finding_bundle.json
├── adjudication_input.json
└── private/
    └── reviewer_notes_input.json
```

`shadow_audit_id` is reproducible over the declared QuantCheck version/code revision, exact audit
report IDs/hashes, execution IDs, and audit context. Runtime is deliberately excluded from that
logical identity, but is included in the finding bundle's content hash and the pilot report.
`audit_context_id` excludes the QuantCheck version and findings; it binds the pseudonymous dataset,
mapping, policy, as-of date, normalized data hashes, point-in-time snapshot hashes, sanitized audit
input hashes, and exact record counts.

## Researcher review and dispositions

The finding bundle is immutable. Reviewers may read it but must never change its `Finding`,
`evidence`, `explanation`, severity, confidence, affected records, source report, or content hash.
Human state lives only in `adjudication_input.json` and the separate private notes input.

Each finding has an independent `investigation_status` and one disposition:

| Disposition | Meaning |
|---|---|
| `confirmed_issue` | the customer determined that the flagged data condition is an issue |
| `legitimate_data_condition` | the evidence is real but correct for the source/business context |
| `accepted_exception` | the condition is accepted under a documented customer decision |
| `duplicate_correlated_signal` | another finding already represents the same or correlated review signal; this is a human disposition, never an inferred QuantCheck match |
| `unresolved` | no supported conclusion has been supplied |

`not_started` must remain `unresolved`, `not_assessed`, and zero review seconds. An investigated
finding may remain unresolved. Set `decision_impact=customer_independently_confirmed` only when the
customer independently confirms that a `confirmed_issue` affected a research decision. QuantCheck
does not infer this fact from a detector, a note, a policy action, or a backtest.

Finalize the sanitized adjudication after all edits:

```sh
python -m quantcheck.external_dataset_shadow adjudicate \
  --bundle /customer-controlled/shadow-review-001/researcher_finding_bundle.json \
  --input /customer-controlled/shadow-review-001/adjudication_input.json \
  --output /customer-controlled/shadow-review-001/adjudication_export.json
```

The command requires exactly one entry for every finding and checks every immutable finding hash.
It exports no evidence, value, customer record ID, dataset name, or reviewer note.

Free-text notes are optional, private, and separately finalized:

```sh
python -m quantcheck.external_dataset_shadow notes \
  --bundle /customer-controlled/shadow-review-001/researcher_finding_bundle.json \
  --input /customer-controlled/shadow-review-001/private/reviewer_notes_input.json \
  --output /customer-controlled/shadow-review-001/private/reviewer_notes.json
```

Reviewer notes are never an input to the pilot report.

## Compare a rerun across QuantCheck versions

Prepare a new finding bundle from the new run rather than altering the first bundle. Then run:

```sh
python -m quantcheck.external_dataset_shadow compare \
  --baseline /customer-controlled/run-v1/researcher_finding_bundle.json \
  --candidate /customer-controlled/run-v2/researcher_finding_bundle.json \
  --output /customer-controlled/comparisons/v1-to-v2.json
```

The versions or code revisions must differ. `audit_context_matches=true` only when the exact
version-independent audit context matches. Comparison uses one documented exact key: detector,
detector ID, fault type/subtype, rule ID, affected record IDs, and canonical evidence hash. It does
no fuzzy matching (`exact_evidence_key_no_fuzzy_matching`). Same key plus identical full finding
hash is `unchanged`; same key plus a
different full finding hash is `changed`; unmatched keys are `added` or `removed`. The comparison
references both original IDs/hashes and never alters either finding.

If `audit_context_matches=false`, report the mapping, policy, data, as-of, or record-context change
alongside the version difference. Do not attribute the finding delta to code alone.

## Design-partner evaluation template

Do not enter estimates, desired targets, synthetic examples, or blank-field defaults as pilot
results. Generate the report only from finalized adjudication exports supplied by the customer
evaluation process:

```sh
python -m quantcheck.external_dataset_shadow report \
  --pilot-key dp-pilot-opaque-001 \
  --bundle /customer-controlled/dataset-1/researcher_finding_bundle.json \
  --adjudication /customer-controlled/dataset-1/adjudication_export.json \
  --bundle /customer-controlled/dataset-2/researcher_finding_bundle.json \
  --adjudication /customer-controlled/dataset-2/adjudication_export.json \
  --output /customer-controlled/pilot-report.json
```

Use the following blank template when agreeing the evaluation. The generated
`quantcheck/shadow-pilot-report/v1` supplies each value mechanically; this document supplies none.

| Evaluation field | Definition and factual source | Supplied pilot result |
|---|---|---|
| Datasets audited | count of unique, identity-verified finding bundle/adjudication pairs | |
| Records audited | sum of point-in-time `snapshot_record_count`; the exact records detectors received, not raw source rows | |
| Runtime | sum of the measured `runtime_ns` supplied in immutable finding bundles | |
| Findings by detector | exact count for each of the four detector keys in complete adjudication exports | |
| Findings investigated | entries explicitly marked `investigated`, including those still unresolved | |
| Confirmed issues | entries disposed `confirmed_issue` | |
| Legitimate exceptions | `legitimate_data_condition` plus `accepted_exception`, with both categories also reported separately | |
| Unexplained/noisy alerts | investigated unresolved findings plus `duplicate_correlated_signal`, with both categories also reported separately | |
| Issues affecting a research decision | confirmed issues whose impact is explicitly `customer_independently_confirmed` | |
| Researcher time reviewing findings | sum of reviewer-supplied `researcher_review_seconds`; not file elapsed time | |

The report also preserves `findings_not_investigated` so unresolved defaults cannot silently become
noise, and it links every aggregate to exact bundle/export hashes. It contains aggregate values
only: no customer or dataset names, findings/evidence, values, customer records, or reviewer notes.
It cannot be generated without at least one dataset and exactly one complete adjudication export
for every supplied bundle.

## Factual reporting and closeout

Before sharing a pilot report:

1. verify all source artifact identities and retain the hash-linked files under the agreed access
   controls;
2. confirm that every reviewed disposition and review-time value was supplied by the approved
   reviewer process;
3. obtain explicit customer confirmation for every counted research-decision impact;
4. state any audit-context mismatch beside rerun comparisons;
5. label the report design-partner evidence, not a benchmark, detector precision/recall result,
   financial-loss estimate, or generalized customer outcome; and
6. obtain customer approval for the aggregate report and apply the agreed retention/deletion plan.

QuantCheck supports generating a factual report from supplied data. This repository contains no
design-partner data, adjudication, review note, pilot report, or manufactured pilot number.
