# QuantCheck project scope

## Problem

Financial research can look convincing because a dataset leaks future information, corrupts scale, double-counts observations, or substitutes later revisions into an earlier historical state.

## Product

QuantCheck is a deterministic Python framework that:

1. builds point-in-time financial snapshots;
2. injects realistic controlled defects;
3. creates a private fault manifest;
4. sanitizes corrupted data for manifest-blind auditing;
5. runs independent detectors;
6. scores findings exactly against the manifest after audit finalization;
7. measures controlled research-output changes;
8. produces reproducible public evidence without exposing private truth.

## Version 0.1 fault families

- Look-Ahead Timestamp
- Unit Drift
- Duplicate Observations
- Revision Overwrite

## Version 0.1 surfaces

- Python package
- deterministic offline fixtures
- narrow SEC Company Facts adapter
- saved benchmark artifacts
- Typer CLI
- read-only Streamlit dashboard
- deterministic HTML summary

## Explicit non-goals

- real-money trading or execution
- alpha, Sharpe, or financial-loss claims
- generic portfolio optimization or backtesting
- authentication, teams, billing, or hosted SaaS
- universal SEC statement reconstruction
- automatic detector-only remediation
- missing-observation and entity-swap faults in v0.1
