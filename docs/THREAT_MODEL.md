# QuantCheck threat and adversarial model

The adversary this design worries about is not a network attacker. It is the
ordinary pressure that makes a benchmark quietly stop measuring what it claims:
an answer key leaking into the detector's input, a held-out seed getting used
during development, a weak group disappearing from a report, or a number in the
README drifting from the artifact it came from.

## T1 — A detector sees the answer key

**Mitigation.** Detectors receive an `AuditInputSnapshot`, produced by
`sanitize_for_audit`, and nothing else. No detector function accepts a
`manifest`, `clean_snapshot`, `seed`, `severity`, or `targets` parameter, and
`run_all_detectors(audit_input, detector_configs)` has no manifest channel.
`dispatch_benchmark_case` finalises the audit report *before* the manifest is
loaded, so the ordering is structural rather than conventional.

**Verified by.** Signature introspection tests; a test asserting the persisted
audit input is byte-identical to `sanitize_for_audit(corrupted_snapshot)`; a
scan asserting audit inputs carry no `seed`, `severity`, `target_count`,
`target_rank`, `expected_count`, `copy_ordinal`, `fault_id`, `manifest_id`,
`selection_digest`, `seed_class`, or `case_kind` field.

## T2 — Held-out seeds stop being held out

Reserved final seeds `1000`–`1009` exist so the release has evidence that was
never used during development. The threat is any path — a flag, an environment
variable, a keyword argument, a forgotten test helper — that lets one run
outside the release path.

**Mitigation.** One authorization primitive, `quantcheck.release_gate`:

* it accepts **exactly** the complete reserved partition and nothing else — a
  subset, superset, duplicate, reordered mix with a development seed, or a seed
  one past either end is refused;
* it is a context manager backed by a `ContextVar`, so permission is scoped to
  a block, removed even if the block raises, and never a global another thread
  or task can observe;
* it refuses to nest, so two candidates cannot be open at once;
* it requires a frozen release candidate identifier, so no authorization is
  anonymous;
* it imports nothing from `quantcheck`, so the package cannot influence it.

The boundary is drawn at **execution**, not representation.
`benchmark_contract.require_seed_execution_authorized` is called by benchmark
configuration building, expansion, the case dispatcher, and all three
saved-stage workflow functions. Deserializing a saved held-out artifact is
allowed, because the public reader, presentation model, HTML summary, and
dashboard must be able to read released evidence and none of them executes
anything.

> This distinction was learned the hard way during the release. An earlier draft
> refused representation too, which made the released public evidence package
> unreadable by the very surfaces built to present it. That candidate was
> invalidated and the fix is pinned by a regression test.

**Verified by.** `tests/test_release_gate.py` and
`tests/test_release_final_seed_rejection.py`: every reserved seed refused at
every execution entry point and through every CLI command; near-miss seeds
(`10`, `99`, `110`, `999`, `1010`, `1100`, `10000`) refused with *and* without
an authorization; mixed partitions refused; a static AST check that only
`release_gate` and `release_run` open an authorization and that `cli.py` never
mentions the gate; and a fresh-subprocess check that the gate starts closed.

## T3 — The release candidate drifts under the evidence

**Mitigation.** A freeze record pins the package version, Python requirement,
benchmark spec version, the release matrix, all four fault specifications,
every severity definition, detector versions/configuration/thresholds, matching
rules, false-positive denominator rules, the replay method, both reviewed
fixture hashes, the normalised release configuration and its canonical hash,
the expanded case matrix hash, and the SHA-256 of all 67 frozen repository
files. Verification is byte-level and refuses to repair; a single drifted byte
invalidates the candidate and the release path refuses to dispatch.

**Verified by.** `tests/test_release_freeze.py` — drifted source, drifted
lockfile, drifted fixture, missing frozen file, tampered identity, and
wrong-configuration cases all raise; `tests/test_release_run.py` — a drifted
input refuses the run with **no output tree created at all**.

## T4 — Weak results quietly disappear

**Mitigation.** Failed and incomplete cases stay in the matrix, in the status
files, and in the aggregate's status totals; they are excluded only from pooled
detection metrics. Every grouping is validated as a total partition of the
configured matrix, so a dropped case makes the aggregate fail validation. The
30 structurally ineligible cases in the 0.1.0 release are reported in full.

## T5 — Metrics drift between artifact and prose

**Mitigation.** The presentation model copies the saved aggregate's own numbers
across rather than recomputing them; metrics stay `Decimal | None` end to end
and never pass through binary float. Documentation quotes exact saved Decimal
strings. `CHECKSUMS.md` covers the frozen source, the freeze record, and every
release document, so a document edited after the fact fails verification.

## T6 — Public evidence leaks private truth

**Mitigation and verification.** See
[ARTIFACTS_AND_PRIVACY.md](ARTIFACTS_AND_PRIVACY.md). Against the released
0.1.0 public-only tree with the private tree physically absent: no private
object key, no local path, no secret marker, no traceback, no symlink, and no
traversable path. The private tree was scanned in the same pass to confirm it
*does* hold `mutation`, `original_value`, `selection_digest`, `entity_name`, and
`target_rank`, so the public scan cannot pass vacuously.

## T7 — Presentation executes science

**Mitigation.** The presentation layer's transitive `quantcheck` import closure
is pinned by test to `benchmark_contract`, `benchmark_store`, `hashing`,
`json_types`, `release_gate`, `schemas`, `serialization`, and `unit_drift_math`
— no manifest, injector, detector, scorer, replay, or research module. The
dashboard and HTML recompute no metric and run no benchmark. There is no
manifest browsing and no private-value browsing.

## Explicitly out of scope

Network attackers, multi-tenant isolation, authentication, authorization of
human users, supply-chain attestation, reproducible-build bit-for-bit
guarantees across platforms, and side-channel resistance. QuantCheck is a local,
single-user, offline research tool.
