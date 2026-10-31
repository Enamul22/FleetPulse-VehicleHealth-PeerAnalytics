"""Frozen target-specific matching; presentation filters never enter this module."""

import numpy as np
import pandas as pd
from .config import SIGNALS, PEER_VERSION

POLICY = dict(
    version=PEER_VERSION,
    minimum_other=2,
    ambient_caliper_c=5.0,
    age_caliper_years=3.0,
    hours_relative_caliper=0.5,
    hours_floor=500.0,
    limited_max=4,
)
MEMBERSHIP_COLUMNS = [
    "vehicle_id",
    "month",
    "peer_id",
    "ambient_difference_c",
    "age_difference_years",
    "hours_difference",
    "hours_limit",
    "reference_version",
]


def eligible_peers(f, target):
    if f.duplicated(["vehicle_id", "month"]).any():
        raise ValueError("Duplicate vehicle/month keys in peer input")
    q = f[
        (f.vehicle_id != target["vehicle_id"])
        & f.month.eq(target["month"])
        & f.model_id.eq(target["model_id"])
        & f.usage_profile.eq(target["usage_profile"])
        & f.health.notna()
    ].copy()
    if pd.isna(target["health"]):
        return q.iloc[:0]
    for col in ["ambient_c", "age_years", "lifetime_engine_hours"]:
        q = q[np.isfinite(q[col])]
        if not np.isfinite(target[col]):
            return q.iloc[:0]
    q["ambient_difference_c"] = (q.ambient_c - target["ambient_c"]).abs()
    q["age_difference_years"] = (q.age_years - target["age_years"]).abs()
    q["hours_difference"] = (q.lifetime_engine_hours - target["lifetime_engine_hours"]).abs()
    q["hours_limit"] = 0.5 * max(target["lifetime_engine_hours"], POLICY["hours_floor"])
    return q[
        (q.ambient_difference_c <= 5.0 + 1e-12)
        & (q.age_difference_years <= 3.0 + 1e-12)
        & (q.hours_difference <= q.hours_limit + 1e-12)
    ].sort_values("vehicle_id")


def build_peers(monthly):
    if monthly.duplicated(["vehicle_id", "month"]).any():
        raise ValueError("Duplicate vehicle/month keys")
    out = monthly.copy()
    out["peer_count"] = 0
    out["peer_health"] = np.nan
    out["peer_support"] = "Unavailable"
    out["peer_reason"] = "Own score unavailable"
    for k in SIGNALS:
        out[k + "_peer"] = np.nan
    membership = []
    # Matching is independent per month/model/profile, using every eligible member.
    for _, g in monthly.groupby(["month", "model_id", "usage_profile"], sort=True):
        for idx, r in g.iterrows():
            if pd.isna(r.health):
                continue
            peers = eligible_peers(g, r)
            n = len(peers)
            out.at[idx, "peer_count"] = n
            out.at[idx, "peer_reason"] = (
                "Fewer than two other eligible vehicles"
                if n < 2
                else "Same month/model/usage; ambient ±5 °C, age ±3 years, lifetime hours ±50% (500 h floor)"
            )
            for p in peers.itertuples():
                membership.append(
                    [
                        r.vehicle_id,
                        r.month,
                        p.vehicle_id,
                        p.ambient_difference_c,
                        p.age_difference_years,
                        p.hours_difference,
                        p.hours_limit,
                        PEER_VERSION,
                    ]
                )
            if n < 2:
                continue
            out.at[idx, "peer_health"] = float(peers.health.mean())
            out.at[idx, "peer_support"] = "Limited (2–4 peers)" if n <= 4 else "Matched comparison"
            for k in SIGNALS:
                out.at[idx, k + "_peer"] = float(peers[k + "_score"].mean())
    out["health_gap"] = out.health - out.peer_health
    out["underperformance"] = out.health_gap.le(-5) & out.peer_health.notna()
    out["peer_version"] = PEER_VERSION
    return out, pd.DataFrame(membership, columns=MEMBERSHIP_COLUMNS)


def component_comparisons(components, monthly):
    c = components.copy()
    lookup = monthly.set_index(["vehicle_id", "month"])
    c["peer_mean"] = [lookup.loc[(r.vehicle_id, r.month), r.component + "_peer"] for r in c.itertuples()]
    c["gap_contribution"] = 0.2 * (c.score - c.peer_mean)
    previous = c[["vehicle_id", "month", "component", "score"]].copy()
    previous["month"] = previous.month + pd.offsets.MonthBegin(1)
    c = c.merge(
        previous.rename(columns={"score": "previous_score"}),
        on=["vehicle_id", "month", "component"],
        how="left",
        validate="one_to_one",
    )
    c["change_contribution"] = 0.2 * (c.score - c.previous_score)
    valid_change = monthly.set_index(["vehicle_id", "month"]).change.notna()
    c.loc[[not valid_change.loc[(r.vehicle_id, r.month)] for r in c.itertuples()], "change_contribution"] = (
        np.nan
    )
    return c
