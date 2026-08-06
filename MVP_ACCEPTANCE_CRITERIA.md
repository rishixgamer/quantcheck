# MVP acceptance criteria

QuantCheck 0.1 is complete only when all of the following are true:

1. Four supported fault families can be injected deterministically.
2. Detectors operate only on sanitized audit inputs and never receive the private manifest.
3. Exact matching reports true positives, false positives, false negatives, precision, recall, F1, and false-positive rate under documented rules.
4. Clean controls are included.
5. At least 120 seeded fault cases plus required controls run through one benchmark protocol.
6. Saved artifacts preserve an enforceable public/private boundary.
7. At least one controlled research output changes because of corruption.
8. Manifest-assisted exact replay restores the clean controlled result for successful cases.
9. The CLI can run the supported saved workflows without editing Python source.
10. The dashboard and HTML read public artifacts only and do not execute scientific logic.
11. Ordinary tests are offline, deterministic, typed, and reproducible across supported hash seeds.
12. README, reports, presentation, and release notes derive their numbers from saved artifacts.
13. Limitations and weak detector results are documented honestly.
14. Wheel and source distribution build successfully and contain no private benchmark truth, caches, secrets, or local paths.

Historical 0.1.0 metrics and hashes are regression references only. They are not acceptance requirements unless the reconstructed contracts and fixtures make exact reproduction both intended and demonstrably valid.
