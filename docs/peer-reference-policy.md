# Peer reference fp-peer-1

A target-specific neighbourhood, not a global cluster. No nearest-N cap or fallback widening is used. All criteria apply to features available in the selected month:

| Rule | Frozen value |
|---|---|
| Own/comparator data | Complete supported five-indicator health |
| Model, month, usage profile | Exact equality |
| Ambient | Difference ≤5 °C in operating-exposure-weighted observed monthly ambient |
| Age | Difference ≤3 years; source age at 2025-01-01 plus elapsed month-end days /365.25 |
| Lifetime engine hours | Absolute difference ≤0.50×max(target lifetime hours, 500 h) |
| Distinct IDs | Exclude target, reject duplicate vehicle/month input |
| Minimum | Two **other** valid distinct vehicles |
| Limited support | Two to four comparators |
| Vote | One equal vote per eligible comparator |

Country does not have to match; ambient is observed scenario context, not a country penalty. Health value itself, hidden component state, fault flags, desired conclusion and current display filters do not select comparators. Eligibility uses data sufficiency, not whether the score looks good. The hours caliper is target-relative, so neighbourhoods need not be symmetric.

Zero/one comparator keeps the actual candidate count/membership but peer overall/component means stay null. Own health remains usable. Invalid own health cannot establish a comparable peer gauge. There is no invented zero average, rank, substitute member, significance claim or precise small-sample percentile.

Mean overall and five mean component scores use exactly the same membership. Contributions `0.20×(own component − peer component mean)` therefore add to the net peer gap before rounding. Comparator operating hours do not change the weight of that comparator’s final score.

Membership is materialized for each target/month in `peer_membership.parquet`, including matching deltas, target hours limit and reference revision. Inspect every comparator in the detail expander. Membership can change monthly: the dashed trend is explicitly named **monthly matched-peer average**, never a fixed cohort. Country/search/score filters are presentation only and cannot affect this saved reference.

Tests exercise zero/one/two, self/duplicates, wrong months, invalid scores, model/profile mismatch, exact caliper boundaries, positive floors, ties, asymmetric target limits, equal votes and future/filter invariance. Counts come from actual rules/data, not a forced peer-availability target. Later matching changes require a new reference revision and explicit recalculation.
