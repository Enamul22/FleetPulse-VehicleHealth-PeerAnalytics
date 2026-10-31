"""Untouched offline evaluation after freezing development calibration/policy."""

import json
import numpy as np
import pandas as pd
from .config import DATA, EVALUATION, SIGNALS
from .baseline import healthy_population, healthy_expectation, predict
from .scoring import score_months
from .reporting import load_data


def scenario(b, seed=9107, loss=0.0, component=None, noise=True):
    """Independent evaluation vehicle configs; never used to choose coefficients or thresholds."""
    f = healthy_population(seed, 31, "EVAL-SCENARIO")
    f["date"] = pd.date_range("2025-01-01", periods=len(f))
    f["month"] = pd.Timestamp("2025-01-01")
    f["vehicle_id"] = "EVAL-CONTROL"
    f["operating_hours"] = 2.0
    f["recorded_fraction"] = 1.0
    f["charging_expected"] = True
    f["rpm"] = f.rpm.clip(lower=850)
    expected = healthy_expectation(f)
    for k, s in SIGNALS.items():
        f[k + "_valid"] = True
        if not noise:
            f[s["signal"]] = expected[k]
        if component is None or k == component:
            f[s["signal"]] += s["direction"] * s["severe"] * loss
    return f


def evaluate(folder=DATA, evaluation=EVALUATION):
    bundle = load_data(folder)
    b = bundle["baseline"]
    m = bundle["vehicle_month_health"]
    c = bundle["component_month_health"]
    # Distinct seed and calibration vehicle IDs; no scored fleet used to fit references.
    held = healthy_population(9101, 12000, "HEALTHY-HOLDOUT")
    truth = healthy_expectation(held)
    reference = {}
    for k, s in SIGNALS.items():
        error = predict(held, b, k) - truth[k]
        observed_error = held[s["signal"]] - predict(held, b, k)
        groups = held[["model_id", "ambient_c", "load"]].copy()
        groups["error"] = error
        groups["ambient_band"] = pd.cut(groups.ambient_c, [-31, -10, 10, 30, 46]).astype(str)
        groups["load_band"] = pd.cut(groups.load, [0.09, 0.4, 0.7, 0.96]).astype(str)
        biases = groups.groupby(["model_id", "ambient_band", "load_band"], observed=True).error.mean()
        reference[k] = dict(
            unit=s["unit"],
            expected_reference_mae=float(np.abs(error).mean()),
            measurement_residual_mae=float(np.abs(observed_error).mean()),
            max_context_mean_error=float(biases.abs().max()),
            healthy_tolerance=b["signals"][k]["healthy_tolerance"],
        )
    monotonic = {}
    recovery = {}
    for k in SIGNALS:
        levels = [0, 0.25, 0.5, 0.75, 1.0]
        scores = []
        for loss in levels:
            mm, cc = score_months(scenario(b, loss=loss, component=k, noise=False), b)
            scores.append(float(cc.set_index("component").loc[k, "score"]))
        assert np.all(np.diff(scores) <= 1e-10) and scores[0] > scores[-1]
        monotonic[k] = dict(loss_levels=levels, component_scores=scores)
        # Same evaluation context/noise, independently generated supported recovery observations.
        low = score_months(scenario(b, loss=0.65, component=k, noise=False), b)[0].health.iloc[0]
        restored = score_months(scenario(b, loss=0.10, component=k, noise=False), b)[0].health.iloc[0]
        assert restored > low
        recovery[k] = dict(before=float(low), after=float(restored), improvement=float(restored - low))
    # Compare independent noise realizations and a single brief adverse daily summary.
    healthy_scores = []
    mean_scores = []
    for seed in range(9200, 9240):
        mm, cc = score_months(scenario(b, seed=seed), b)
        healthy_scores.append(float(mm.health.iloc[0]))
        mean_scores.append(float(cc.mean_only_score.mean()))
    base = scenario(b, noise=False)
    mm, cc = score_months(base, b)
    spike = base.copy()
    spike.loc[0, "oil_c"] += 28
    sm, sc = score_months(spike, b)
    burst = base.copy()
    burst.loc[:1, "oil_c"] += 28
    bm, bc = score_months(burst, b)
    # Full measured invariants, before display rounding.
    supported = c[c.score.notna()]
    reconstructed = supported.groupby(["vehicle_id", "month"]).own_deduction.agg(["sum", "count"])
    idx = m.set_index(["vehicle_id", "month"])
    complete = reconstructed[reconstructed["count"] == 5]
    own_error = float((complete["sum"] - (100 - idx.loc[complete.index, "health"])).abs().max())
    gap = c.groupby(["vehicle_id", "month"]).gap_contribution.sum(min_count=5)
    expected_gap = idx.health_gap
    gap_error = float((gap - expected_gap).abs().max())
    change = c.groupby(["vehicle_id", "month"]).change_contribution.sum(min_count=5)
    change_error = float((change - idx.change).abs().max())
    assert max(own_error, gap_error, change_error) < 1e-9
    membership = bundle["peer_membership"]
    assert not membership.duplicated(["vehicle_id", "month", "peer_id"]).any()
    assert (membership.vehicle_id != membership.peer_id).all()
    counts = []
    for month, g in m.groupby("month"):
        valid = g.health.notna()
        counts.append(
            dict(
                month=month.strftime("%Y-%m"),
                assets=len(g),
                own_score=int(valid.sum()),
                peer_comparison=int(g.peer_health.notna().sum()),
                valid_own_no_peers=int((valid & g.peer_count.eq(0)).sum()),
                valid_own_one_peer=int((valid & g.peer_count.eq(1)).sum()),
                limited_2_to_4=int((g.peer_health.notna() & g.peer_count.between(2, 4)).sum()),
                unknown=int((~valid).sum()),
            )
        )
    dec = m[m.month.eq(pd.Timestamp("2025-12-01"))]

    def first(g):
        return g.vehicle_id.iloc[0] if len(g) else None

    examples = dict(
        healthy=first(dec.sort_values("health", ascending=False)),
        declining=first(dec.dropna(subset=["change"]).sort_values("change")),
        rebounded=first(dec.dropna(subset=["change"]).sort_values("change", ascending=False)),
        missing=first(dec[dec.health.isna()]),
        no_peers=first(dec[dec.health.notna() & dec.peer_count.eq(0)]),
        one_peer=first(dec[dec.health.notna() & dec.peer_count.eq(1)]),
        limited=first(dec[dec.peer_count.between(2, 4) & dec.peer_health.notna()]),
    )
    report = dict(
        evaluation_seed=9101,
        evaluation_vehicles="HEALTHY-HOLDOUT and EVAL-CONTROL; independent of training/development and displayed fleet",
        reference_errors=reference,
        controlled_deterioration=monotonic,
        supported_recovery=recovery,
        noise_sensitivity=dict(
            tail_aware_health_mean=float(np.mean(healthy_scores)),
            tail_aware_health_std=float(np.std(healthy_scores)),
            mean_only_health_mean=float(np.mean(mean_scores)),
            mean_only_health_std=float(np.std(mean_scores)),
            single_day_oil_spike_overall_deduction=float(mm.health.iloc[0] - sm.health.iloc[0]),
            two_day_oil_burst_overall_deduction=float(mm.health.iloc[0] - bm.health.iloc[0]),
        ),
        max_reconstruction_error=dict(own=own_error, peer_gap=gap_error, monthly_change=change_error),
        month_availability=counts,
        examples=examples,
        score_summary={k: float(v) for k, v in m.health.describe().items()},
        interpretation="Synthetic index checks, not real-world diagnostic accuracy. Tail-aware settings remain the approved 70/30 policy; evaluation results did not refit or tune them.",
    )
    path = __import__("pathlib").Path(evaluation)
    path.mkdir(parents=True, exist_ok=True)
    (path / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
