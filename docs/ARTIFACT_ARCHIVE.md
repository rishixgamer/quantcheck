# Artifact archive and release assets

This manifest describes the boundary between the public source tree and
immutable archive or release assets. The curation changed the tip only; it did
not rewrite Git history. The pre-curation commit remains the provenance record
for material removed from the default branch.

## In-tree research artifacts

The research narratives, protocols, adjudications, CSV summary, and
publication package are retained under [`docs/research/`](research/). Their
content and scientific claims were not rewritten for presentation; only
repository-relative links and execution paths were updated.

## Release-only or archive-only payloads

The following payloads are intentionally absent from the public tip because
they are large, raw, or generated media. They are attached to the immutable
[`portfolio-evidence-2026-08-24` GitHub release](https://github.com/rishixgamer/quantcheck/releases/tag/portfolio-evidence-2026-08-24).
The SHA-256 values below are
the content digests of the exact downloadable assets, not claims about the
current working tree:

| Payload | Reason absent from tip | Immutable release asset | SHA-256 |
| --- | --- | --- |
| Narrated demo video | Large generated binary | [`QuantCheck_demo.mp4`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/QuantCheck_demo.mp4) | `a24834c1b1ad432450a8e2a50dcd3e47a37d51817a0e8189d2ce041eb4072788` |
| Real-data evidence archive | Raw fetched responses, cache metadata, and expanded study payloads | [`quantcheck-real-data-evidence-2026-08-13.tar.gz`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/quantcheck-real-data-evidence-2026-08-13.tar.gz) | `cad16cb14f7110571470530e5b16398a1eafc903bea5f092496f52d4d4e6dd98` |
| Development orchestration archive | Historical orchestration logs and handoff material | [`quantcheck-development-orchestration-archive.tar.gz`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/quantcheck-development-orchestration-archive.tar.gz) | `25b4f266a4a78d8cbe9ce1d1a0f29a1e80e2c35bb1a8614f1da68d4c5aea7f7` |

The release tag and assets are immutable publication evidence. Consumers must
verify the downloaded bytes against the SHA-256 values above and must not infer
that omitted raw payloads are available in the source tree.

## Retained evidence

Small study summaries remain in `evidence/real_data_study/`, including
`applicability.json`, `study_run.json`, and each company's source, snapshot,
sanitized audit input, and detector execution. The adversarial study retains
its public reports, run summary, and separately scoped private manifests.
These summaries do not certify natural SEC error rates or customer outcomes.
