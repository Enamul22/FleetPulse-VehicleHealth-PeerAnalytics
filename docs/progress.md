# Engineering decisions and verification history

## Baseline and synthetic data

FleetPulse extends the canonical FleetCare asset and usage data with a coherent daily component-performance history. Canonical source revision: `0f3663e31ea6610eb2a00256ca0d984ebc7c586b`. Persistent component trajectories, weather/context variation, sensor gaps and labelled synthetic interventions support offline evaluation.

A separate healthy development population fits the frozen ridge reference. Observable operating conditions explain the expected signal; age, country and hidden condition labels are excluded from score inference. Evaluation labels remain separate from application inputs.

## Scoring and peers

Five component scores combine exposure-weighted mean and tail severity using a 70/30 policy. Coverage thresholds determine whether an overall score is available. Exact additive contributions explain deductions, peer gaps and month-to-month changes.

Peer matching uses target-specific model, usage, ambient, age and lifetime-hour criteria. The target vehicle is excluded, and comparisons require at least two other vehicles. Sparse and unavailable comparisons are explicitly labelled.

## Interface

The overview supports monthly review, search, filters, pagination and full filtered export. Vehicle details show own/peer gauges, a four-month trend, component comparisons, peer membership, evidence and score arithmetic. Navigation preserves review context.

## Verification record

The implementation review recorded 35 passing tests, offline scoring validation and desktop/phone walkthroughs. GitHub CI and an independent Python 3.12.14 clean clone passed the same 35 tests, locked installation and Streamlit startup checks. See [verification.md](verification.md) for measured outcomes and sensitivity analysis.

[Scoring reference](scoring-baseline-card.md) · [Peer policy](peer-reference-policy.md) · [Reproducibility](reproducibility.md)
