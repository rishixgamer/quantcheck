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
they are large, raw, or generated media. The tag and release URLs below identify
the publication, while each SHA-256 value binds the exact downloaded content.
GitHub release assets are mutable, so verify the bytes against the portable
[`SHA256SUMS.txt`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/SHA256SUMS.txt)
manifest as well as the values recorded here:

| Payload | Reason absent from tip | Release asset URL | SHA-256 content binding |
| --- | --- | --- | --- |
| Narrated demo video | Large generated binary | [`QuantCheck_demo.mp4`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/QuantCheck_demo.mp4) | `a24834c1b1ad432450a8e2a50dcd3e47a37d51817a0e8189d2ce041eb4072788` |
| Real-data evidence archive | Raw fetched responses, cache metadata, and expanded study payloads | [`quantcheck-real-data-evidence-2026-08-13.tar.gz`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/quantcheck-real-data-evidence-2026-08-13.tar.gz) | `cad16cb14f7110571470530e5b16398a1eafc903bea5f092496f52d4d4e6dd98` |
| Development orchestration archive | Historical orchestration logs and handoff material | [`quantcheck-development-orchestration-archive.tar.gz`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/quantcheck-development-orchestration-archive.tar.gz) | `25b4f266a4a78d8cbe9ce1d1a0f29a1e80e2c35bb1a8614f1da68d4c5aea7f7b` |
| Real-data private-manifest archive | Private answer-key manifests for the adversarial study | [`quantcheck-real-data-substrate-private-manifests-2026-08-13.tar.gz`](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/quantcheck-real-data-substrate-private-manifests-2026-08-13.tar.gz) | `577e3f6ed5b84cfdcc13448df4fc7a4b6407d17c42889dbbadb19d41691dce97` |

The release tag identifies the publication; the recorded SHA-256 values bind
the asset content even if a GitHub asset is replaced. Consumers must verify the
downloaded bytes against those values and must not infer that omitted raw
payloads are available in the source tree.

## Retained evidence

Small study summaries remain in `evidence/real_data_study/`, including
`applicability.json`, `study_run.json`, and each company's source, snapshot,
sanitized audit input, and detector execution. The adversarial study retains
its public reports and run summary; its private manifests are preserved only in
the release-hosted private-manifest archive above and are not tracked here.
These summaries do not certify natural SEC error rates or customer outcomes.
