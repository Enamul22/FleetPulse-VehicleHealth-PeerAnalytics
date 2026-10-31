# Verification report

FleetPulse 1.0.0 / fp-daily-1 / fp-index-1 / fp-peer-1. Python 3.12.14, locked environment. This report distinguishes measured local/evaluation/browser results from remote CI and manual hosting.

## Local automated checks

**35 passed**, zero skips, including eight Streamlit AppTest cases. Ruff lint and format checks passed; `pip check` reported no dependency conflicts. [JUnit evidence](evidence-tests.xml).

Coverage includes complete 1,000-row monthly grids / 12,000 unique vehicle-months / 60,000 component-months; source counter/exposure consistency; all prepared checksums; replay scoring from shipped observations; weighted inverse-CDF semantics and exposure mean; clipping, robust tolerance/zero spread; no/low usage, active-day/hour/80% boundaries, missing channels, sensor/context validity; model/weather/load reference invariance; country/age/truth/future independence; deterioration/recovery; peer zero/one/two/self/duplicates/caliper boundaries/wrong month/equal votes; additive own/peer/month-change reconstruction; full filters/pages/CSV; hash-seed/fresh-process generator/calibration reproducibility.

Streamlit tests cover default December, no auth/database form even with irrelevant database variables set, overview/detail, filters/sort/page restored by Back, both gauges agreeing with saved rows, September's June–September trend, healthy/declining/rebounded/missing/no-peer/one-peer/limited examples, and honest unavailable gauges/narratives. Browser native selection is recorded separately below.

## Independent held-out evaluation

Training/development seeds 4101/4102 are frozen before evaluation. Healthy holdout seed 9101 uses separate identities; controlled scenario seed 9107 and 40 noise realizations 9200–9239 do not fit policy settings. Full machine-readable results: [validation.json](../data/evaluation/validation.json).

| Signal | Expected-reference MAE | Unit | Max context mean error |
|---|---|---|---|
| charging | 0.000687 | V | 0.002491 |
| cooling | 0.020126 | °C | 0.039707 |
| lubrication | 0.001272 | bar | 0.003251 |
| oil | 0.027003 | °C | 0.087166 |
| smoothness | 0.002606 | mm/s RMS | 0.007847 |

These errors compare fitted reference to the held-out simulator's known healthy expectation. They are not real-vehicle accuracy or failure detection rates. Measurement residual MAEs, units and healthy tolerances are also recorded in JSON. Controlled adverse perturbation could not improve any affected component across five levels; supported recovery improved overall health for all five tested component scenarios.

Maximum exact arithmetic errors (points): own deductions **1.78e-14**, peer gap **4.8e-14**, monthly change **2.04e-14**.

Forty independent healthy noise realizations: tail-aware mean **99.998967**, standard deviation **0.002862**; mean-only mean **99.998525**, standard deviation **0.004089**. A single severe oil-summary day reduced overall index by **0.451** points; two such days reduced it by **6.899**. The empirical tail boundary can amplify sustained/burst exposure above 5%; it is not universally smoother than a mean. Approved 70/30 settings were retained, not tuned to evaluation outcomes.

## Actual monthly sufficiency / reference availability

| Month | Assets | Own score | Peer comparison | Unknown own | Valid own / zero peers | Valid own / one peer | Limited 2–4 |
|---|---|---|---|---|---|---|---|
| 2025-01 | 1000 | 893 | 838 | 107 | 13 | 42 | 142 |
| 2025-02 | 1000 | 903 | 850 | 97 | 17 | 36 | 139 |
| 2025-03 | 1000 | 896 | 849 | 104 | 13 | 34 | 135 |
| 2025-04 | 1000 | 903 | 853 | 97 | 12 | 38 | 144 |
| 2025-05 | 1000 | 908 | 871 | 92 | 6 | 31 | 141 |
| 2025-06 | 1000 | 910 | 874 | 90 | 11 | 25 | 142 |
| 2025-07 | 1000 | 905 | 865 | 95 | 12 | 28 | 129 |
| 2025-08 | 1000 | 903 | 873 | 97 | 10 | 20 | 135 |
| 2025-09 | 1000 | 914 | 887 | 86 | 5 | 22 | 132 |
| 2025-10 | 1000 | 894 | 861 | 106 | 7 | 26 | 113 |
| 2025-11 | 1000 | 898 | 858 | 102 | 5 | 35 | 114 |
| 2025-12 | 1000 | 907 | 874 | 93 | 7 | 26 | 121 |

Availability was not forced. All unscorable vehicles/months are retained; a valid own score remains independent of comparator availability. Known source usage was not overwritten to manufacture no-driving examples; those are separate boundary fixtures.

## Browser, clean clone and remote CI

Final browser evidence, independent locked clean-clone run and actual GitHub CI are appended after execution. Streamlit hosting remains deliberately undeployed. The app entry point is `app.py`; manual deployment requires Python 3.12 and **no Secrets**.

### Completed browser review

Chrome against the actual local Streamlit process, using native row-selection checkboxes and separate month/detail/back controls. Full desktop information/health/comparison/interpretation panels were reviewed and saved. Search reduced the display to a single row while retaining its original multi-vehicle peer reference.

| December example | Verified state |
|---|---|
| VEH-0001 | 70.3 own / 74.3 peer; −3.9 gap; two other peers, explicitly limited; negative terms and positive offsets agree |
| VEH-0383 | 98.4 own, +13.8 versus 12 matched peers; no invented underperformance |
| VEH-0852 | 70.6 own, −9.5 monthly change, −9.7 versus 18 peers; declining trend agrees |
| VEH-0457 | 88.7 own, +8.6 monthly change; one comparator leaves peer gauge unavailable; no causal repair assertion |
| VEH-0015 | Overall/peer gauges unavailable, known previous months visible with December gap; recorder coverage reason displayed |
| VEH-0331 | Valid own 71.3, zero eligible peers; own history retained and no substitute comparison |

The direct responsive-control API timed out. Review continued through Chrome's native DevTools device toolbar: **390×844** verified; stacked asset cards, score panels, trend and wrapped explanation text stayed within the narrow layout. Device emulation/DevTools were then closed and normal desktop restored. This was an actual browser preview, not an AppTest claim about pixel layout.

Screenshots are indexed in [screenshots/README.md](screenshots/README.md). Initial captures use the tab screenshot; native fallback captures include Chrome context/device dimensions. No screenshots expose credentials. No application functionality depends on the browser-control tools.

### Clean clone and remote CI completed

- Application commit **e59b7e1** was pushed using verified Enamul22 SSH identity and repository-local Enamul Haque author configuration. [GitHub Actions run 41191728743](https://github.com/Enamul22/FleetPulse-VehicleHealth-PeerAnalytics/actions/runs/41191728743) completed **successfully**. Job logs inspected through Enamul's selected GitHub connection show **35 passed in 7.81 seconds**, with successful locked install, dependency consistency, Ruff and offline validation steps. No secrets, database or reference repository were supplied to CI.
- A fresh SSH clone in an independent temporary directory installed the full lock into a new **Python 3.12.14** environment. `pip check`, lint and format checks passed; **35 tests passed in 27.16 seconds**. The clone contained no private Streamlit Secrets or sibling FleetCare checkout.
- Actual `python -m streamlit run app.py` startup from that clone returned healthy and HTTP 200 on its independent local test port. The clean environment's AppTest cases loaded the included prepared bundle and exercised overview/detail/navigation/gauges/explanations. The temporary clean-clone server was stopped after verification.
- Both completed reference working trees were rechecked clean. FleetPulse made no live database connection/provisioning/write, copied no credentials or sessions, and changed no reference application/deployment. All implementation/data/test/docs changes are confined to its sibling repository.
- **Hosting is not deployed.** Remaining manual step: create the new Streamlit app from `main`, entry point `app.py`, Python 3.12; **leave Secrets empty**. Read-only data ships in the repository.
