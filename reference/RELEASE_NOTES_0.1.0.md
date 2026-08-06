# QuantCheck 0.1.0 release notes

QuantCheck 0.1.0 is a local Python framework for testing whether point-in-time financial research data can manufacture misleading results through timestamp leakage, unit corruption, duplicate observations, or revision-history failure.

The frozen final matrix contains 120 fault cases and 12 clean controls. All 132 cases completed. Across 170 injected fault units, the strict micro metrics are precision `0.6680161943319838056680161943`, recall `0.9705882352941176470588235294`, F1 `0.7913669064748201438848920862`, and false-positive rate `0.04029484029484029484029484029`. The benchmark recorded 165 true-positive faults, five false-negative faults, and 82 false-positive findings. All 12 clean controls produced zero findings.

The strongest primary result was duplicate observations at precision/recall/F1 `1`/`1`/`1`. Look-ahead and revision-overwrite cases each had recall `1` and precision `0.5` because their correlated temporal contract violations produced visible cross-detector findings under strict single-label scoring. Unit drift had precision `0.6140350877192982456140350877` and recall `0.875`; its immediate-neighbor rule missed five injected faults and sometimes attributed a discontinuity to the adjacent clean observation.

Controlled research output changed in 107 of 120 fault cases. Every one of the 120 successful fault cases reproduced the clean research result after manifest-assisted exact replay. This is controlled replay evidence, not automatic remediation or a trading-performance claim.

The release benchmark ID is `e5a1770a7599c76d628769fbc8d534f7e3807f455241d8a5306299100ae811bc`; aggregate report ID is `6606132b146a24300dc55ce67e6ef8cb5995c2628b2c371c7c30e4d4fa6225b9`. Full exact results and limitations are in `docs/FINAL_BENCHMARK_RESULTS.md`.

This release is intentionally narrow: one reviewed synthetic benchmark fixture, four fault families, day-level end-of-day semantics, a small one-CIK synchronous SEC adapter, local execution, and public read-only presentation. It does not reconstruct statements, provide detector-only repair, certify vendors, prevent financial losses, or demonstrate trading alpha.

