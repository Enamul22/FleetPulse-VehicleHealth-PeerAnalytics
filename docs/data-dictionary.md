# Data dictionary

All months are first-of-month timestamps, sorted by actual date, January–December 2025. Daily dates are UTC day labels without invented intraday precision. Null score ≠ zero score.

| Prepared file | Grain / principal fields |
|---|---|
| assets.parquet | 1,000 canonical vehicles, CRM/customer/model/location IDs, source age/initial counters, usage profile; derived name/type |
| observations.parquet | 365,000 vehicle/days; canonical hours/distance/end counters; model/ambient/load/RPM, charging_expected, recorded_fraction, five observed signals and five validity flags, extension provenance |
| vehicle_month_health.parquet | Exactly 12,000 vehicle/month keys; source totals/end counters, month-end age, exposure-weighted ambient, five component scores, overall/null, prior-month index/change, coverage/status, leading deductions, peer means/count/support/reason/gap/underperformance, versions and joined asset context |
| component_month_health.parquet | Exactly 60,000 vehicle/month/indicator keys; observed/expected/adverse weighted means, weighted mean/p95 severity, burden, own/mean-only scores, total/valid/unrecorded/unsupported/invalid-sensor hours, valid active days, coverage/reason, weight-0.20 own deduction, peer component mean/gap contribution, previous component and comparable change contribution |
| peer_membership.parquet | Target/month/comparator key; distinct other IDs, ambient/age/hour differences, target hour limit and reference revision. Candidates of size one retained for honest counts; no mean until ≥2 |
| baseline.json | Frozen observable feature names/scales, context bounds, per-signal coefficients, directions, tolerance/severe/unit, development errors/seeds and method |
| policy.json | Fixed five weights, 70/30 aggregation, weighted percentile semantics, sufficiency gates, measurement bounds, peer calipers/minimum, bands/5-point display threshold and versions |
| manifest.json | Original source revision/blob hashes, interface reference revision, seeds, source/extension distinction, complete row/entity counts and prepared file SHA256s |

| Offline-only file | Meaning |
|---|---|
| simulator_truth.parquet | Hidden monthly component loss per vehicle/month/indicator, explicitly separate from inference |
| synthetic_interventions.parquet | Hidden component intervention date and independent synthetic provenance; no live service linkage |
| validation.json | Untouched evaluation metrics, controlled checks, reconstruction errors, monthly availability and review example IDs |

Signal units: oil/coolant °C, pressure bar, charging voltage V, vibration mm/s RMS. Load is a fraction; operating/lifetime exposures are hours; distance/counters km. `adverse_mean` is an exposure-weighted nonnegative residual in the signal’s unit, before tolerance/severity mapping. It is not a raw peer temperature difference.

`coverage` is valid supported recorded operating hours divided by known monthly operating hours. Overall coverage is the minimum across the five required indicators. Active source days at vehicle grain differ from valid days at component grain. Missing recorder exposure, invalid sensors and unsupported context are separately inspectable.

`health_gap = health − peer_health`; negative is below peers. `change = health − previous_health` only for a consecutive calendar month with both complete indices. No gap is bridged across missing months. Per-component peer means use identical membership; missing overall health never receives a reweighted five-component substitute.
