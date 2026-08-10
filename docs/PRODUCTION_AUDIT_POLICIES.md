# Production audit policy contract

## Boundary and identity

`AuditPolicyV1` (`quantcheck/audit-policy/v1`, ID prefix `apol_`) configures
production audits only. It is not a `BenchmarkConfig`, `BenchmarkV2Config`, or
`DetectorExecutionConfigV2`, and no benchmark accepts it. Conversely, the
production audit entry points require an `AuditPolicyV1`; there is no active
module-level policy, environment-variable override, or implicit customer
default.

Each policy contains a caller-assigned `policy_name` and `policy_version`, plus
two derived identities:

- `policy_content_hash` is the SHA-256 of the exact normalized canonical policy
  content;
- `policy_id` is a stable `apol_` identity in the dedicated policy namespace.

Both are validated when the policy is constructed and again before an audit.
Unknown fields fail closed. Logically unordered collections are normalized, so
reordering them does not change bytes; changing a version, action, enablement,
threshold, expectation, exception, or reason changes both identities.

Policies contain no manifest, fault, seed, target, clean/corrupted record,
benchmark identity, score, or other hidden-truth field. They operate only over
the existing sanitized `AuditInputSnapshot` and public detector findings.

## Configured behavior

Every policy explicitly lists all four supported detector rules exactly once.
Each entry contains `enabled`, an action (`blocking`, `warning`, or
`informational`), and an explicit disablement reason when disabled. An enabled
Unit Drift rule must state its `ratio_threshold`; this is the only current
detector contract with a configurable threshold. Its supported scale factors
remain the frozen scientific contract. Look-Ahead, Duplicate Observations, and
Revision Overwrite admit no threshold override, so supplying one is rejected.

Production expectation rules are separate from frozen detectors:

- concept/unit rules give a non-empty accepted-unit set for one exact concept
  namespace/concept and optional entity scope;
- publication-lag rules give a minimum and maximum number of days for exactly
  one of `filing_after_period_end`, `availability_after_filing`, or
  `availability_after_period_end`;
- reporting-frequency rules give an exact concept scope, period type, and
  maximum gap between adjacent distinct period ends in the same exact
  entity/concept/unit/dimension/period-shape series.

Availability-based lag rules run only because `DatasetMappingV1` admits an
evidenced end-of-day availability column or evidenced equality to filing. A
future mapping variant without those semantics must be rejected rather than
treated as if the rule passed. A frequency rule with fewer than two distinct
period ends is recorded as `not_evaluated` with
`insufficient_distinct_periods`; it is not silently reported as clean. The
frequency contract detects internal gaps only. Without a policy reporting
window it does not claim that a first or last expected filing is absent.

## Exceptions and precedence

Dataset exceptions require an exact `dataset_name`, a configured enabled
`rule_id`, an explicit effect, and a non-blank reason. Optional record, entity,
concept, and unit predicates can narrow the exception. An exception either
waives the action or replaces it with another explicit action. It never removes
the detector finding or policy result: reports retain the base action,
effective action, exception ID, effect, and reason.

Resolution is deterministic and tested in this order:

1. Mapping, input, normalized-artifact, audit-boundary, policy-schema, and
   identity validation are absolute gates. Exceptions cannot catch or downgrade
   malformed input or integrity failures.
2. Explicit detector enablement decides which frozen detectors execute.
   Disabled rules remain in the report with their required reason.
3. Enabled detectors and expectation rules evaluate the sanitized input. Every
   configured rule is recorded as `evaluated`, `not_evaluated`, or `disabled`.
4. Exceptions match only an existing result with the exact dataset and rule.
   The matching exception with the greatest number of exact scope predicates
   wins. Equally specific matches are ambiguous and fail the audit closed.
5. Active actions determine disposition: any blocking result yields `blocked`;
   otherwise any warning yields `review_required`; otherwise informational
   results yield `passed_with_information`; otherwise the audit `passed`.
   Waived results remain counted separately.

Tuple order, policy declaration order, working directory, environment, and
Python hash seed have no precedence effect.

## Report provenance

The production API emits `ExternalDatasetAuditReportV2`
(`quantcheck/external-audit/v2`, ID prefix `xaudit2_`). Every report records the
exact `policy_id`, `policy_name`, `policy_version`, and `policy_content_hash`,
the enabled detectors and resolved public detector configuration, every
unchanged nested detector report, every rule status, all active and exception-
applied results, action/waiver counts, and final disposition. Report identity
covers all of those fields.

`ExternalDatasetAuditReportV1` remains only as an additive historical parsing
type for artifacts produced before policies existed. No current production
entry point emits it. Migration is a new explicit audit under a chosen policy,
not an in-place rewrite.

## Representative policies

`quantcheck.external_dataset_policy_examples` exposes two factories:

- `monitoring_policy_v1()` runs all detectors with informational actions and
  the explicit frozen Unit Drift threshold;
- `illustrative_governed_policy_v1()` demonstrates detector disablement,
  blocking/warning actions, all expectation types, a threshold, and a reasoned
  dataset exception using deliberately fictional taxonomy and dataset names.

They are examples, not recommendations or active defaults, and contain no real
customer requirement. Callers must explicitly pass the returned policy.
