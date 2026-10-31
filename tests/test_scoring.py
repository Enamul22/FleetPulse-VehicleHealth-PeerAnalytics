import numpy as np
import pandas as pd
import pytest
from fleetpulse.baseline import tolerance, predict
from fleetpulse.config import SIGNALS
from fleetpulse.scoring import weighted_percentile, severity, score_months


def test_weighted_inverse_cdf_ties_and_denominators():
    assert weighted_percentile([1, 0], [5, 95]) == 0
    assert weighted_percentile([0, 1], [94.9, 5.1]) == 1
    assert weighted_percentile([1, 1, 5], [2, 2, 0]) == 1
    assert weighted_percentile([np.nan, 3], [100, 1]) == 3
    assert np.isnan(weighted_percentile([1], [0]))
    with pytest.raises(ValueError):
        weighted_percentile([1], [1], 1.1)
    with pytest.raises(ValueError):
        weighted_percentile([1, 2], [1])


def test_severity_floors_outliers_and_clipping():
    np.testing.assert_allclose(severity(np.array([-5, 0, 2, 6, 20]), 2, 10), [0, 0, 0, 0.5, 1])
    with pytest.raises(ValueError):
        severity([1], 2, 2)
    assert tolerance(np.zeros(100), 0.2) == 0.2
    x = np.random.default_rng(31).normal(0, 1, 10000)
    assert abs(tolerance(x, 0.1) - tolerance(np.r_[x, 1e9], 0.1)) < 0.01


def test_exposure_aggregation_not_calendar_weighting(baseline, observations):
    f = observations.copy()
    f["operating_hours"] = 1.0
    # One daily summary above severe reference, with 10x exposure; all other summaries healthy.
    f.loc[0, "operating_hours"] = 10.0
    f.loc[0, "oil_c"] += 28
    m, c = score_months(f, baseline)
    oil = c.set_index("component").loc["oil"]
    sev = severity(
        28 + f.loc[0, "oil_c"] - 28 - predict(f.iloc[:1], baseline, "oil")[0],
        baseline["signals"]["oil"]["healthy_tolerance"],
        28.0,
    )
    assert oil.mean_severity == pytest.approx(float(sev) * 10 / 40)
    assert oil.tail95_severity == pytest.approx(float(sev))
    assert oil.score == pytest.approx(100 * (1 - 0.7 * oil.mean_severity - 0.3 * oil.tail95_severity))
    assert m.health.iloc[0] == pytest.approx(c.score.mean())
    # Engine-off calendar days have zero weight and cannot improve the score.
    f.loc[1:, "operating_hours"] = 0.0
    _, c = score_months(f, baseline)
    assert c.set_index("component").loc["oil", "status"] == "Fewer than five active days"


@pytest.mark.parametrize(
    "change,reason",
    [
        ("zero", "No operating exposure"),
        ("low", "Less than ten supported hours"),
        ("days", "Fewer than five active days"),
        ("coverage", "Less than 80% valid exposure"),
        ("context", "Outside reference context"),
        ("sensor", "Less than 80% valid exposure"),
    ],
)
def test_sufficiency_retains_unknowns(baseline, observations, change, reason):
    f = observations.copy()
    if change == "zero":
        f.operating_hours = 0.0
    if change == "low":
        f.operating_hours = 9.9 / len(f)
    if change == "days":
        f.operating_hours = 0.0
        f.loc[:3, "operating_hours"] = 6.0
    if change == "coverage":
        f.recorded_fraction = 0.7999
    if change == "context":
        f.ambient_c = 50.0
    if change == "sensor":
        f.oil_valid = False
    m, c = score_months(f, baseline)
    assert pd.isna(m.health.iloc[0]) and reason in m.data_status.iloc[0]
    if change == "sensor":
        assert c.score.notna().sum() == 4


def test_exact_80_percent_and_all_five_required(baseline, observations):
    f = observations.copy()
    f.recorded_fraction = 0.8
    m, c = score_months(f, baseline)
    assert pd.notna(m.health.iloc[0]) and np.allclose(c.coverage, 0.8)
    f["oil_c"] = np.nan
    m, c = score_months(f, baseline)
    assert pd.isna(m.health.iloc[0]) and c.score.notna().sum() == 4
    # A physically invalid value does not masquerade as severe condition.
    f = observations.copy()
    f.oil_c = 9999.0
    assert pd.isna(score_months(f, baseline)[0].health.iloc[0])


def test_country_truth_and_future_invariance(baseline, observations):
    f = observations.copy()
    m, c = score_months(f, baseline)
    changed = f.assign(country="Another country", hidden_loss=1.0, intended_recovery=True)
    pd.testing.assert_frame_equal(m, score_months(changed, baseline)[0])
    sep = f.copy()
    sep = sep.iloc[:30].copy()
    sep["date"] = pd.date_range("2025-09-01", periods=30)
    sep["month"] = pd.Timestamp("2025-09-01")
    dec = f.copy()
    dec["date"] = pd.date_range("2025-12-01", periods=31)
    dec["month"] = pd.Timestamp("2025-12-01")
    full = pd.concat([sep, dec], ignore_index=True)
    computed = score_months(full, baseline)[0]
    earlier = computed[computed.month.eq(pd.Timestamp("2025-09-01"))].reset_index(drop=True)
    full.loc[full.month.eq(pd.Timestamp("2025-12-01")), "oil_c"] += 15
    computed = score_months(full, baseline)[0]
    pd.testing.assert_frame_equal(
        earlier, computed[computed.month.eq(pd.Timestamp("2025-09-01"))].reset_index(drop=True)
    )
    # September followed by December is not a previous-month comparison.
    assert score_months(full, baseline)[0].change.isna().all()
    assert not any("country" in x or "hidden" in x for x in baseline["features"])


def test_controlled_deterioration_and_recovery(baseline, observations):
    for k, s in SIGNALS.items():
        results = []
        for loss in [0, 0.25, 0.5, 0.75, 1]:
            f = observations.copy()
            f[s["signal"]] += s["direction"] * s["severe"] * loss
            c = score_months(f, baseline)[1].set_index("component")
            results.append(c.loc[k, "score"])
        assert np.all(np.diff(results) <= 1e-9) and results[-1] < results[0]
        assert results[0] > results[3]


def test_input_integrity(baseline, observations):
    with pytest.raises(ValueError, match="Duplicate"):
        score_months(pd.concat([observations, observations]), baseline)
    f = observations.copy()
    f.loc[0, "operating_hours"] = -1
    with pytest.raises(ValueError, match="exposure"):
        score_months(f, baseline)


def test_context_reference_healthy_weather_load_and_model_invariance(baseline):
    from fleetpulse.baseline import healthy_population, healthy_expectation

    f = healthy_population(9317, 2400, "CONTEXT-HOLDOUT")
    expected = healthy_expectation(f)
    for k, s in SIGNALS.items():
        error = predict(f, baseline, k) - expected[k]
        assert np.abs(error).mean() < 0.1 * s["noise"]
        assert np.abs(error).max() < 0.3 * s["noise"]
    assert f.oil_c[f.ambient_c > 30].mean() > f.oil_c[f.ambient_c < 0].mean()
    # Country/age and simultaneous sensor deterioration do not change healthy expectations.
    p = predict(f, baseline, "oil")
    f = f.assign(country="Elsewhere", age_years=99, coolant_c=999, pressure_bar=0)
    np.testing.assert_array_equal(p, predict(f, baseline, "oil"))


def test_exact_five_days_ten_hours_boundary(baseline, observations):
    f = observations.copy()
    f.operating_hours = 0.0
    f.loc[:4, "operating_hours"] = 2.0
    m, c = score_months(f, baseline)
    assert pd.notna(m.health.iloc[0]) and c.valid_hours.eq(10).all() and c.active_days.eq(5).all()
