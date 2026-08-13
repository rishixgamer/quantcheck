# QuantCheck demo production package

## Finished cut

`QuantCheck_demo.mp4` is the finished 2:56 portfolio cut. The system voice is
replaceable: record a human version against `narration.txt` and keep the timing
from `captions.vtt`.

## Timestamped shot list

| Time | Screen | Narration focus | Cursor / zoom |
|---|---|---|---|
| 00:00–00:10 | Hook slide: equity curve, future arrow | A mathematically correct backtest can still be wrong if its data knew the future. | No cursor; 105% push-in. |
| 00:10–00:23 | Three-date timeline: Mar 31, Apr 15, May 2 | Reporting period, research date, and actual filing date are different. | Animate left to right; hold on Apr 15 → May 2 gap. |
| 00:23–00:35 | Clean versus corrupted availability cards | The future filing is stamped available too early. | Highlight the corrupted `Available on` field. |
| 00:35–00:46 | Clean versus corrupted research screen | The controlled ranking changes because an unavailable observation enters the screen. | Static crop; no investment-performance implication. |
| 00:46–01:07 | Manifest-blind audit-boundary diagram | Detectors receive only a sanitized snapshot; hidden truth enters after audit finalization. | Slow pan toward the locked manifest; stop before it. |
| 01:07–01:16 | Four fault-family cards | Look-Ahead Timestamp, Unit Drift, Duplicate Observations, Revision Overwrite. | Glide across cards. |
| 01:16–01:33 | Saved benchmark evidence card | 124 cases: 120 faults, 4 controls; 94 succeeded; 30 structural failures; 0 incomplete. | Hold metrics readable. |
| 01:33–01:58 | Public evidence dashboard | 130 injected faults, 208 findings, precision 0.625, recall 1.0, F1 0.769, FPR about 7.29%; 78 false positives retained. | No cursor; dashboard crop only. |
| 01:58–02:13 | SEC-substrate adversarial result | 120 manufactured faults exactly matched; 4 correlated Unit Drift warnings retained. | Crossfade from exact matches to warnings. |
| 02:13–02:29 | Narrow real-data exposure card | 472 selected SEC Company Facts records from five issuers; 0 duplicate groups among 472 singleton fingerprints. | Static crop. |
| 02:29–02:42 | Applicability table | Three detectors had zero eligible opportunities; this is not broad natural-data validation. | Hold the `NOT APPLICABLE` labels. |
| 02:42–02:56 | Closing card | Ask whether research data had the right information, at the right time, in the right form. | No cursor; fade out. |

## Exact narration

The authoritative spoken copy is in `narration.txt`; it is generated from the
same scene data used to build the MP4. The first and last lines are:

> A backtest can be mathematically correct and still be wrong if its data knew
> the future.

> QuantCheck asks a prior question: whether the data beneath a backtest,
> ranking, or research conclusion had the right information, at the right time,
> in the right form.

## Onscreen text and captions

The MP4 carries readable slide text throughout. `captions.vtt` supplies the
matching caption track. Keep these qualifiers visible whenever the relevant
numbers appear:

- “Saved v0.1 evidence — reviewed synthetic fixture.”
- “Manufactured faults on preserved SEC observations.”
- “Narrow real public-data study.”
- “Pipeline exposure, not broad natural-data validation.”

## Visual asset list

- `build/svg/` — editable slide SVGs.
- `build/png/` — 1920×1080 rendered slide frames.
- `docs/assets/quantcheck-hero.svg` — audit boundary.
- `docs/assets/benchmark-results.svg` — benchmark evidence.
- `docs/assets/demo-dashboard.svg` — public evidence dashboard.
- `docs/assets/real-substrate-results.svg` — adversarial real-substrate result.
- Custom slides — hook, point-in-time timeline, fault, consequence, four fault
  families, real-data exposure, applicability, and ending.

## Recording and replacement checklist

- [ ] Record at 16:9, 1920×1080, 30 fps.
- [ ] Replace the system voice only after matching `narration.txt` exactly.
- [ ] Keep captions and the evidence qualifiers in the final export.
- [ ] Do not show installation, source scrolling, terminal commands, private
  manifests, raw pre-corruption values, secrets, or local paths.
- [ ] Keep benchmark values tied to the saved v0.1 fixture evidence.
- [ ] Keep the real-data applicability distinction visible.
- [ ] Listen for mispronunciations of “QuantCheck”, “Company Facts”, “Unit
  Drift”, “Revision Overwrite”, and “no-eligible-target”.

Retake a shot if a zero opportunity count is presented as a successful detector
test, if “no findings” is presented as “no errors”, if false positives vanish,
or if the SEC study sounds like customer or production validation.

## 30-second shortened version

“A backtest can be mathematically correct and still be wrong if its data knew
the future. A reporting period can end on March 31 while the result is not filed
until May 2; treating it as available on April 15 leaks the future. QuantCheck
injects controlled faults and audits only a sanitized snapshot, without giving
detectors the private answer key. It tests Look-Ahead Timestamp, Unit Drift,
Duplicate Observations, and Revision Overwrite. Its saved evidence keeps
failures and false positives visible—and asks whether the data behind
quantitative research deserves to be trusted.”

## Portfolio embed copy

**Title:** QuantCheck — Auditing Point-in-Time Financial Research Data

**Description:** QuantCheck is a deterministic audit framework for testing
whether financial research data can manufacture misleading results through
look-ahead leakage, unit drift, duplicate observations, or revision-history
failure. This demo shows the point-in-time problem, the manifest-blind audit
boundary, saved benchmark evidence, an explicitly retained limitation, and a
narrow real SEC Company Facts exposure study. The real-data result demonstrates
pipeline execution and a limited duplicate-observation null result; it is not
broad natural-data detector validation or investment advice.
