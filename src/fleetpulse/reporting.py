"""Immutable prepared reporting; display filters cannot change scores or membership."""

import hashlib, json, math
from pathlib import Path
import pandas as pd
from .config import DATA, SIGNALS


def load_data(folder=DATA):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    for name in [
        "vehicle_month_health.parquet",
        "component_month_health.parquet",
        "peer_membership.parquet",
        "assets.parquet",
        "baseline.json",
        "policy.json",
    ]:
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != manifest["sha256"][name]:
            raise ValueError("Prepared file checksum mismatch; regenerate the complete versioned bundle")
    frames = {
        k: pd.read_parquet(folder / (k + ".parquet"))
        for k in ["vehicle_month_health", "component_month_health", "peer_membership", "assets"]
    }
    m = frames["vehicle_month_health"]
    a = frames["assets"]
    if m.duplicated(["vehicle_id", "month"]).any() or not a.vehicle_id.is_unique:
        raise ValueError("Duplicate prepared keys")
    expected = set(a.vehicle_id)
    if any(set(g.vehicle_id) != expected for _, g in m.groupby("month")):
        raise ValueError("Every month must retain every canonical asset")
    return {
        **frames,
        "manifest": manifest,
        "baseline": json.loads((folder / "baseline.json").read_text()),
        "policy": json.loads((folder / "policy.json").read_text()),
    }


def overview(bundle, month):
    # The prepared monthly grid retains even unscorable rows; left join protects canonical assets.
    month = pd.Timestamp(month)
    m = bundle["vehicle_month_health"]
    f = m[m.month.eq(month)].copy()
    if len(f) != len(bundle["assets"]):
        raise ValueError("Month is outside the prepared complete grid")
    return f.reset_index(drop=True)


def filter_rows(frame, filters):
    f = frame.copy()
    q = filters.get("search", "").strip()
    if q:
        text = f[["vehicle_id", "vehicle_name", "customer_name", "city"]].fillna("").agg(" ".join, axis=1)
        f = f[text.str.contains(q, case=False, regex=False)]
    for key in ["model_id", "country", "usage_profile"]:
        value = filters.get(key, "All")
        if value != "All":
            f = f[f[key].eq(value)]
    band = filters.get("band", "All")
    if band == "Unavailable":
        f = f[f.health.isna()]
    elif band == "90–100":
        f = f[f.health.ge(90)]
    elif band == "75–<90":
        f = f[f.health.ge(75) & f.health.lt(90)]
    elif band == "0–<75":
        f = f[f.health.lt(75)]
    if filters.get("use_range"):
        lo, hi = filters.get("range", (0, 100))
        mask = f.health.between(lo, hi)
        if filters.get("include_unavailable", True):
            mask |= f.health.isna()
        f = f[mask]
    peers = filters.get("peers", "All")
    if peers == "Available":
        f = f[f.peer_health.notna()]
    elif peers == "Unavailable":
        f = f[f.peer_health.isna()]
    elif peers == "Limited (2–4)":
        f = f[f.peer_count.between(2, 4) & f.peer_health.notna()]
    if filters.get("underperformance"):
        f = f[f.underperformance]
    order = filters.get("sort", "Health · lowest first")
    col, ascending = {
        "Health · lowest first": ("health", True),
        "Health · highest first": ("health", False),
        "Peer gap · lowest first": ("health_gap", True),
        "Vehicle ID": ("vehicle_id", True),
        "Change · lowest first": ("change", True),
    }[order]
    return f.sort_values(
        [col, "vehicle_id"] if col != "vehicle_id" else [col],
        ascending=[ascending, True] if col != "vehicle_id" else [True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def page_slice(f, page, size=25):
    count = max(1, math.ceil(len(f) / size))
    page = min(max(1, int(page)), count)
    return f.iloc[(page - 1) * size : page * size].copy(), page, count


def trend(bundle, vehicle, month):
    end = pd.Timestamp(month)
    start = max(pd.Timestamp("2025-01-01"), end - pd.DateOffset(months=3))
    f = bundle["vehicle_month_health"]
    f = f[f.vehicle_id.eq(vehicle) & f.month.between(start, end)]
    return (
        f.set_index("month").reindex(pd.date_range(start, end, freq="MS")).rename_axis("month").reset_index()
    )


def detail(bundle, vehicle, month):
    f = overview(bundle, month)
    row = f[f.vehicle_id.eq(vehicle)]
    if len(row) != 1:
        raise ValueError("Unknown vehicle")
    c = bundle["component_month_health"]
    c = c[c.vehicle_id.eq(vehicle) & c.month.eq(pd.Timestamp(month))].copy()
    p = bundle["peer_membership"]
    p = p[p.vehicle_id.eq(vehicle) & p.month.eq(pd.Timestamp(month))].copy()
    members = p.merge(
        f[
            ["vehicle_id", "model_id", "country", "age_years", "lifetime_engine_hours", "ambient_c", "health"]
        ].rename(columns={"vehicle_id": "peer_id"}),
        on="peer_id",
        how="left",
        validate="many_to_one",
    )
    c["component"] = pd.Categorical(c.component, list(SIGNALS), ordered=True)
    return row.iloc[0].to_dict(), c.sort_values("component"), members.sort_values("peer_id")
