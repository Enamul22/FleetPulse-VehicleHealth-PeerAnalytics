"""Pure observation scoring and exposure aggregation. No simulator truth inputs."""

import numpy as np
import pandas as pd
from .baseline import predict
from .config import SIGNALS, VERSION, MEASUREMENT_BOUNDS

GATES = dict(coverage=0.80, active_days=5, hours=10.0)


def weighted_percentile(values, weights, q=0.95):
    v = np.asarray(values, float)
    w = np.asarray(weights, float)
    if not 0 <= q <= 1 or len(v) != len(w):
        raise ValueError("Invalid weighted percentile arguments")
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
    v = v[ok]
    w = w[ok]
    if not len(v):
        return float("nan")
    order = np.argsort(v, kind="stable")
    v = v[order]
    w = w[order]
    return float(v[min(np.searchsorted(np.cumsum(w), q * w.sum(), side="left"), len(v) - 1)])


def severity(adverse, tolerance, severe):
    if not np.isfinite(tolerance) or not np.isfinite(severe) or severe <= tolerance:
        raise ValueError("Invalid severity calibration")
    return np.clip((np.maximum(adverse, 0) - tolerance) / (severe - tolerance), 0, 1)


def observation_evidence(f, baseline):
    out = f[["vehicle_id", "date", "month", "operating_hours", "recorded_fraction"]].copy()
    supported = f.model_id.isin(["ALD", "BIR", "CED", "ELM"])
    for col, (lo, hi) in baseline["bounds"].items():
        supported &= f[col].between(lo, hi)
    eligible = (f.operating_hours > 0) & (f.rpm >= 800) & f.charging_expected.astype(bool)
    out["context_supported"] = supported
    out["eligible"] = eligible
    for k, s in SIGNALS.items():
        expected = predict(f, baseline, k)
        observed = f[s["signal"]].to_numpy(float)
        ok = (
            supported
            & eligible
            & f[k + "_valid"].astype(bool)
            & np.isfinite(observed)
            & f[s["signal"]].between(*MEASUREMENT_BOUNDS[k])
            & f.recorded_fraction.between(0, 1)
        )
        signed = s["direction"] * (observed - expected)
        out[k + "_observed"] = observed
        out[k + "_expected"] = expected
        out[k + "_adverse"] = np.maximum(signed, 0)
        out[k + "_severity"] = severity(
            signed, baseline["signals"][k]["healthy_tolerance"], baseline["signals"][k]["severe_reference"]
        )
        out[k + "_weight"] = np.where(ok, f.operating_hours * f.recorded_fraction, 0.0)
    return out


def score_months(observations, baseline):
    if observations.duplicated(["vehicle_id", "date"]).any():
        raise ValueError("Duplicate daily observations")
    if not np.isfinite(observations.operating_hours).all() or (observations.operating_hours < 0).any():
        raise ValueError("Operating exposure must be known, finite and non-negative")
    e = observation_evidence(observations, baseline)
    components = []
    monthly = []
    for (vid, month), g in e.groupby(["vehicle_id", "month"], sort=True, observed=True):
        denom = float(g.operating_hours.sum())
        row = dict(
            vehicle_id=vid,
            month=month,
            operating_hours=denom,
            active_days=int((g.operating_hours > 0).sum()),
            policy_version=VERSION,
        )
        scores = []
        reasons = []
        coverages = []
        for k, s in SIGNALS.items():
            weights = g[k + "_weight"].to_numpy()
            valid = weights > 0
            hours = float(weights.sum())
            days = int(valid.sum())
            coverage = hours / denom if denom > 0 else 0.0
            unsupported = float(g.loc[~g.context_supported, "operating_hours"].sum())
            reason = (
                "No operating exposure"
                if denom <= 0
                else "Outside reference context"
                if unsupported / max(denom, 1e-12) > 0.2
                else "Less than 80% valid exposure"
                if coverage < GATES["coverage"] - 1e-12
                else "Fewer than five active days"
                if days < GATES["active_days"]
                else "Less than ten supported hours"
                if hours < GATES["hours"]
                else "Supported"
            )
            mean = float(np.average(g.loc[valid, k + "_severity"], weights=weights[valid])) if hours else None
            tail = weighted_percentile(g[k + "_severity"], weights) if hours else None
            burden = 0.7 * mean + 0.3 * tail if hours else None
            score = 100 * (1 - burden) if reason == "Supported" else None

            def avg(col):
                return float(np.average(g.loc[valid, col], weights=weights[valid])) if hours else None

            components.append(
                dict(
                    vehicle_id=vid,
                    month=month,
                    component=k,
                    label=s["label"],
                    unit=s["unit"],
                    score=score,
                    burden=burden,
                    mean_severity=mean,
                    tail95_severity=tail,
                    mean_only_score=100 * (1 - mean) if score is not None else None,
                    coverage=coverage,
                    valid_hours=hours,
                    total_hours=denom,
                    unsupported_hours=unsupported,
                    unrecorded_hours=float(
                        (g.operating_hours * (1 - g.recorded_fraction.fillna(0).clip(0, 1))).sum()
                    ),
                    invalid_sensor_hours=max(
                        0.0,
                        float(
                            (g.operating_hours * g.recorded_fraction.fillna(0).clip(0, 1))
                            .where(g.context_supported & g.eligible, 0)
                            .sum()
                        )
                        - hours,
                    ),
                    active_days=days,
                    status=reason,
                    observed_mean=avg(k + "_observed"),
                    expected_mean=avg(k + "_expected"),
                    adverse_mean=avg(k + "_adverse"),
                    own_deduction=0.2 * (100 - score) if score is not None else None,
                    policy_version=VERSION,
                )
            )
            row[k + "_score"] = score
            scores.append(score)
            reasons.append(reason)
            coverages.append(coverage)
        row["health"] = sum(0.2 * x for x in scores) if all(x is not None for x in scores) else None
        row["coverage"] = min(coverages)
        row["data_status"] = (
            "Supported"
            if row["health"] is not None
            else "; ".join(dict.fromkeys(r for r in reasons if r != "Supported"))
        )
        row["leading_deduction"] = (
            SIGNALS[list(SIGNALS)[int(np.argmin(scores))]]["label"]
            if row["health"] is not None and min(scores) < 99.95
            else "No material deduction"
            if row["health"] is not None
            else "Insufficient evidence"
        )
        monthly.append(row)
    m = pd.DataFrame(monthly).sort_values(["vehicle_id", "month"]).reset_index(drop=True)
    # Shift within a complete month grid; never skip a missing calendar month.
    previous = m.groupby("vehicle_id", sort=False).health.shift()
    previous_month = m.groupby("vehicle_id", sort=False).month.shift()
    consecutive = pd.to_datetime(m.month) - pd.to_datetime(previous_month)
    m["previous_health"] = previous.where(consecutive.dt.days.between(28, 31))
    m["change"] = m.health - m.previous_health
    return m, pd.DataFrame(components)
