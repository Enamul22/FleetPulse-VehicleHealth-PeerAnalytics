# Scoring and healthy-context baseline card

Score revision **fp-index-1**; extension **fp-daily-1**. This is a hand-defined synthetic observational index, not an empirical failure-risk model. Five signal-derived indicators have equal weight 0.20. No maintenance, country, age, driving-style or rank penalty is added.

## Development and freezing

Known-healthy synthetic populations are separate from the displayed vehicles: training seed 4101, 300 calibration identities × 60 contexts = 18,000 observations; development seed 4102, 150 identities × 60 = 9,000. Models and persistent sensor offsets belong to each identity. Context spans all four models, ambient −30 to 45 °C, load 0.10–0.95 and RPM 700–4,200. Eligibility additionally requires charging expected, positive operating exposure and RPM ≥800.

For each signal, Ridge alpha 0.000001, no fitted intercept, SVD solver. The explicit feature vector is constant, BIR/CED/ELM model indicators (ALD reference), ambient/20, load fraction, RPM/1,000, RPM×load/1,000 and ambient×load/20. These interactions follow the declared synthetic healthy equations. No other target sensor is a predictor, so simultaneous signal deterioration cannot be explained away. Scaling/features/coefficients are transparent JSON; fitting is offline only.

Development context errors did not justify Huber or more complex models. The baseline is deliberately simple for this known linear synthetic mechanism; it is not an outlier-proof reference for arbitrary telemetry. Coefficients and tolerance derivation freeze before fleet scoring and held-out evaluation. Seeds 9101/9107 and 9200–9239 provide independent evaluation identities/scenarios, not parameter selection. Healthy simulator labels select development samples only; displayed hidden condition/intervention labels are never inference inputs.

Signed adverse residual is `direction × (observed − expected)`; excess has +1 direction, deficits −1. Use `max(0, signed residual)` for severity. Tolerance is max(unit floor, median(signed development residual) + 3×1.4826×MAD). Robust scale avoids one extreme reference residual dominating normalization; nonzero floors handle zero spread. The unit-specific severe references are fixed development perturbation settings. Their only interpretation is the scale of this index.

See the generated parameter table below and `data/prepared/baseline.json` for complete coefficients/errors. Physical sensor validity bounds are in `policy.json`; invalid measurements lose exposure rather than appearing as a confirmed component problem.

## Exposure / aggregation

A day is an operating summary, not an invented intraday sample. Weight = canonical observed operating hours × recorded fraction, after eligibility/context/sensor checks. Zero operating days have zero weight. Missing/invalid values cannot dilute a score through a calendar-day mean.

For positive finite weights, sort severity ascending (stable tie handling). The weighted 95th percentile is the first severity where cumulative weight is ≥95% of total valid exposure, without interpolation. At values [0,1] and weights [95,5], p95 is 0; with [94.9,5.1], it is 1. This boundary is tested. Component burden is 70% weighted mean +30% weighted p95; score is 100×(1−burden). Health requires all five component scores and is their weighted sum, bounded 0–100. Missing channels never gain a larger remaining weight.

Gates per component: ≥80% valid exposure over known monthly operating exposure, ≥5 valid active days and ≥10 supported recorded hours. Exact boundaries are tested. The prepared rows retain total/valid/unrecorded/unsupported/invalid-sensor hours, active days and reason. Unsupported conditions are excluded rather than extrapolated; insufficient support yields null output. No month is normalized against its own best vehicle. No future month enters another month’s feature or cohort.

## Interpretation and limitations

Own score reduction and peer shortfall are separate quantities. Five fixed-weight deductions reconstruct 100−health. Five same-membership component gaps reconstruct health−peer mean. Positive terms offset negative terms; the narrative calls out both. Component change attribution is available only where both complete monthly indices exist. Short display rounding does not define the conclusion.

Demonstration bands: 90–100 small deviation, 75–<90 some deviation, below 75 larger deviation. Underperformance filter: gap ≤−5 points with valid peers. These are transparent display categories, not service thresholds or safety decisions.

Tail-aware aggregation is more responsive when adverse summaries exceed about 5% of operating exposure; it can change sharply near the empirical percentile boundary. Held-out checks compare it with mean-only scoring, including one-day/two-day perturbations. Equal weights, 70/30 and severe references are approved demonstration choices, not tuned to a preferred fleet score distribution or validated real-world outcomes.

Methodological building blocks: [NIST MAD](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/mad.htm), [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html), [HuberRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.HuberRegressor.html). These support methods and alternatives; they do not validate this index’s weights or effectiveness on real vehicles.

## Frozen numeric parameters

| Indicator | Unit | Healthy tolerance | Severe reference | Independent expected-reference MAE |
|---|---|---|---|---|
| Oil thermal behaviour | °C | 3.342894 | 28 | 0.027003 |
| Cooling behaviour | °C | 2.445539 | 20 | 0.020126 |
| Lubrication behaviour | bar | 0.239503 | 1.8 | 0.001272 |
| Charging behaviour | V | 0.182271 | 1.7 | 0.000687 |
| Mechanical smoothness | mm/s RMS | 0.337286 | 3 | 0.002606 |
