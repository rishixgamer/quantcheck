# Real-data-substrate adversarial warning adjudication

## Scope

The existing exact scorers matched all 120 injected faults and retained four
additional Unit Drift warnings as false positives. This table records human
review without changing the score. The category describes why the warning
appeared in the injected case; it is not a claim about a natural SEC defect.

| Seed | Finding ID | Affected non-target record | Entity / concept / period end | Related injected target(s) in same exact series | Human category | Evidence and conclusion |
| ---: | --- | --- | --- | --- | --- | --- |
| 101 | `find_fb43514ffe3ba92b` | `rec_ab6cfb0ad65f4a7f` | Alphabet / Assets / 2022-12-31 | `rec_268c5ff05f924116`, `rec_9513e6c442ca1db3` | correlated/redundant warning | The affected record was not an injected target and was a declared neighbor of both targets. The warning proposed a ×1000 correction only after the seeded mutations; the clean Unit Drift control had zero findings. |
| 202 | `find_fd07fd8c5d1e148b` | `rec_63e6d1cdcf13c430` | Alphabet / NetIncomeLoss / 2024-09-30 | `rec_657a991f65ee506f` | correlated/redundant warning | The affected record was not an injected target and was a declared neighbor of the target. The warning appeared only in the injected case; the clean control had zero findings. |
| 303 | `find_23b8ef22f6d73001` | `rec_ac2f96bf85a49b88` | Amazon / NetIncomeLoss / 2019-03-31 | `rec_ccb5a0d662b2e2b9` | correlated/redundant warning | The affected record was not an injected target and was a declared neighbor of the target in the same exact series. The clean control had zero findings. |
| 303 | `find_8a34a83e7d3d8390` | `rec_57add02292ef4ff8` | Apple / NetIncomeLoss / 2024-06-29 | `rec_a1a95b159f8b584d`, `rec_8f8889331cc9290c` | correlated/redundant warning | The affected record was not a target; it was a declared neighbor of one target and in the exact series of another. The clean control had zero findings. |

## Supporting evidence

For each row, the public audit report preserves the detector-visible record,
exact series key, observed value, candidate correction, local ratios, and
neighbor IDs. The private manifest preserves the original and corrupted target
records, exact mutation, series record IDs, and eligible neighbor IDs.

| Seed | Public audit report | Public strict score | Private relationship evidence |
| ---: | --- | --- | --- |
| 101 | `evidence/real_data_substrate_adversarial/public/unit_drift/seed-101/audit_report.json` | `evidence/real_data_substrate_adversarial/public/unit_drift/seed-101/score_report.json` | `evidence/real_data_substrate_adversarial/private/unit_drift/seed-101/manifest.json` |
| 202 | `evidence/real_data_substrate_adversarial/public/unit_drift/seed-202/audit_report.json` | `evidence/real_data_substrate_adversarial/public/unit_drift/seed-202/score_report.json` | `evidence/real_data_substrate_adversarial/private/unit_drift/seed-202/manifest.json` |
| 303 | `evidence/real_data_substrate_adversarial/public/unit_drift/seed-303/audit_report.json` | `evidence/real_data_substrate_adversarial/public/unit_drift/seed-303/score_report.json` | `evidence/real_data_substrate_adversarial/private/unit_drift/seed-303/manifest.json` |

## Evidentiary separation

- **QuantCheck detected:** four extra scale-discontinuity warnings on non-target
  records, in addition to the 36 exact Unit Drift target matches.
- **Human review concluded:** each extra warning was mechanically induced by
  one or more seeded neighboring target mutations and is a correlated signal.
- **Uncertain:** how often comparable correlated warnings would occur under
  other target densities, severities, concepts, or naturally corrupted data.

The exact scorer's classification remains four false positives. Human review
does not convert them to true positives or remove them from reported precision.
