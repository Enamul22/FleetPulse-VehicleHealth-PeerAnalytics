# Dataset and simulator card

## Canonical source

FleetCare main revision `0f3663e31ea6610eb2a00256ca0d984ebc7c586b`, read-only `git show` of `data/demo/assets.parquet` and `daily.parquet`. Source blob SHA256s are in `manifest.json`. Preserve vehicle/CRM/customer/model/location IDs, source age/initial counters, usage profiles and every 2025 daily operating hour, distance, odometer and lifetime-hour value. Exactly 1,000 assets, 201 customer IDs, four models/countries, 365 days each. Names combine the existing fictional model with vehicle ID; Compact/Sedan/Van/Utility types are a documented derived model taxonomy, not new source measurements.

The overview/detail navigation and restrained teal presentation follow the ServicePlan interface pattern.

Original monthly files describe usage/counters, not a complete coherent twelve-month component history. Earlier condition approximations and their shared seasonal weather are deliberately not scored as equivalent observations.

## Separate FleetPulse extension fp-daily-1

Seed 20261029, stable SHA256-derived RNG per vehicle, sorted source iteration. Generate **observations first**:

- Canonical operating exposure/counters stay unchanged. New sensor/context fields are FleetPulse synthetic operating summaries.
- Ambient has a seasonal term, stable city shift, fictional country scenario offsets (Finland −4, Germany +3, United Kingdom +1, Spain +7 °C), and an evolving AR weather disturbance. These are declared scenario choices, not measured national climate statistics. Scoring reads observed ambient, never country.
- Load depends on the canonical usage profile plus stable vehicle/daily variation. RPM follows observable load with noise. Charging expected is explicit while operating.
- Each component has independent initial latent loss, gradual drift, occasional acceleration and optional synthetic intervention. Sensor observations combine the model/context-dependent healthy equation, adverse signal displacement, persistent sensor offset and serial noise. No health score/curve is sampled or read directly from hidden condition.
- Interventions reduce the hidden component loss; resulting observable readings may improve. They have their own synthetic provenance, not real ServicePlan feedback. No frontend explanation reads intended intervention outcomes.
- Independent recorder outages preserve known usage but set recorded fraction to zero; they mean **no recorded measurements**, not a claim that the vehicle did not drive. Monthly missing channels, invalid sensor summaries and rare unsupported ambient contexts produce honest unavailable outputs.
- Daily context/sensors have declared measurement precision: ambient/temperatures 0.01 °C, load/recorded fraction 0.0001, RPM 0.1, pressure/voltage/vibration 0.001. New observation fields use compact float32; source counters/exposure remain original precision. Scoring aggregates these exact shipped observations.

Operational daily summaries are eligible with positive operating hours, RPM ≥800, charging expected and supported model/context. Signal validity additionally requires the sensor flag, finite values, allowed physical measurement bounds and recorded fraction. Unsupported exposure is excluded; the frozen sufficiency gates decide whether the month can be compared.

## Grains / separation

Prepared data includes 365,000 daily observations, 12,000 vehicle-month rows, 60,000 component-month rows, canonical assets and target-specific memberships. Every asset/month key remains even with null outputs. Prepared source/score/reference hashes are versioned together.

`data/evaluation/simulator_truth.parquet` stores hidden monthly component loss. `synthetic_interventions.parquet` stores independently labelled events. These are offline validation artifacts; app imports/data loading never read them. `validation.json` reports independent held-out scenarios and measured fleet integrity/availability; it does not fit scores or feed explanations.

No usage and low usage are also exercised as independent boundary fixtures without changing canonical fleet usage to manufacture examples. Actual included months exhibit recorder/sensor gaps and unsupported contexts. No target score prevalence, attractive curve distribution or peer count is enforced.

## Limitations

This is coherent synthetic evidence from a declared mechanism, not real telemetry validation. Daily summaries cannot establish intraday peaks, exact event times, part failures or causal maintenance effects. A context-adjusted signal deviation can justify inspection, not identify a defective part. The simple healthy equations make reference fitting tractable; generalization to real vehicles is unproven. Approximate source ages are advanced consistently from a stated reference date, not exact birthdays.
