# QuantCheck documentation

This index keeps the public repository navigable without duplicating the technical documents.

| Reader goal | Start here |
| --- | --- |
| Understand the thesis and evidence boundary | [Root README](../README.md) |
| Read the research narrative | [Research paper](research/QUANTCHECK_RESEARCH_PAPER.md) |
| Check which public numbers are permitted | [Evidence ledger](research/QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md) |
| Understand the scientific method | [Methodology](METHODOLOGY.md) |
| Inspect the public/private boundary | [Artifacts and privacy](ARTIFACTS_AND_PRIVACY.md), [Threat model](THREAT_MODEL.md) |
| Inspect a fault contract | [Fault catalogue](faults/) |
| Review benchmark evidence | [Final benchmark results](FINAL_BENCHMARK_RESULTS.md), [v0.2 benchmark](BENCHMARK_V0_2.md) |
| Review real-data evidence | [Research archive](research/README.md), [observational study](research/REAL_DATA_RESULTS.md), [real-substrate adversarial study](research/REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md) |
| Run the local surfaces | [CLI contract](CLI_CONTRACT.md), [Dashboard and HTML](DASHBOARD_AND_HTML.md) |
| Reproduce artifacts | [Reproducibility](REPRODUCIBILITY.md) |
| Understand external inputs | [External datasets](EXTERNAL_DATASETS.md), [production policies](PRODUCTION_AUDIT_POLICIES.md) |
| Understand current implementation status | [Current status](STATUS.md) |

## Reading order

For a research review, read the README, methodology, evidence ledger, benchmark results, real-data results, and limitations in that order. For implementation work, start with [current status](STATUS.md), then follow [the authority and reading order](AUTHORITY_AND_READING_ORDER.md).

## Evidence conventions

Synthetic benchmark results, observational real-source execution, and manufactured faults on real-source substrate are separate evidence classes. A zero finding count is not automatically a negative result: detector-specific applicability and denominators are part of every interpretation.
