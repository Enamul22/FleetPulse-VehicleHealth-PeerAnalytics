"""Reproducible offline source import, generation, calibration, scoring and matching."""

import argparse, hashlib, io, json, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
from .config import (
    ROOT,
    DATA,
    EVALUATION,
    FLEETCARE_REF,
    SERVICEPLAN_REF,
    MODELS,
    VERSION,
    SIM_VERSION,
    SIGNALS,
    MEASUREMENT_BOUNDS,
)
from .baseline import calibrate
from .simulation import extend
from .scoring import score_months, GATES
from .peers import build_peers, component_comparisons, POLICY


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_source(repo):
    blobs = {
        n: subprocess.check_output(["git", "-C", str(repo), "show", f"{FLEETCARE_REF}:data/demo/{n}.parquet"])
        for n in ["assets", "daily"]
    }
    a = pd.read_parquet(io.BytesIO(blobs["assets"]))[
        [
            "vehicle_id",
            "crm_asset_id",
            "customer_id",
            "customer_name",
            "model_id",
            "country",
            "city",
            "age_years",
            "initial_odometer_km",
            "initial_engine_hours",
            "usage_profile",
        ]
    ]
    d = pd.read_parquet(io.BytesIO(blobs["daily"]))[
        ["vehicle_id", "date", "operating_hours", "distance_km", "odometer_km", "lifetime_engine_hours"]
    ]
    assert a.vehicle_id.is_unique and not d.duplicated(["vehicle_id", "date"]).any()
    assert (d.operating_hours >= 0).all() and (d.distance_km >= 0).all()
    a["vehicle_name"] = a.model_id.map(MODELS) + " · " + a.vehicle_id
    a["vehicle_type"] = a.model_id.map({"ALD": "Compact", "BIR": "Sedan", "CED": "Van", "ELM": "Utility"})
    return a, d, {n: hashlib.sha256(b).hexdigest() for n, b in blobs.items()}


def build(a, d, output=DATA, evaluation=EVALUATION, source_hashes=None, baseline=None):
    output = Path(output)
    evaluation = Path(evaluation)
    output.mkdir(parents=True, exist_ok=True)
    evaluation.mkdir(parents=True, exist_ok=True)
    b = baseline or calibrate()
    # Baseline freezes before the displayed fleet is generated/scored.
    (output / "baseline.json").write_text(json.dumps(b, indent=2, sort_keys=True) + "\n")
    obs, truth, events = extend(a, d)
    m, c = score_months(obs, b)
    usage = (
        obs.groupby(["vehicle_id", "month"], sort=True)
        .agg(
            distance_km=("distance_km", "sum"),
            odometer_km=("odometer_km", "last"),
            lifetime_engine_hours=("lifetime_engine_hours", "last"),
        )
        .reset_index()
    )
    weather = (
        obs.assign(ambient_exposure=obs.ambient_c * obs.operating_hours)
        .groupby(["vehicle_id", "month"])
        .agg(ambient_exposure=("ambient_exposure", "sum"), hours=("operating_hours", "sum"))
        .reset_index()
    )
    weather["ambient_c"] = weather.ambient_exposure / weather.hours.replace(0, np.nan)
    m = m.merge(usage, on=["vehicle_id", "month"], validate="one_to_one").merge(
        weather[["vehicle_id", "month", "ambient_c"]], on=["vehicle_id", "month"], validate="one_to_one"
    )
    m = m.merge(a, on="vehicle_id", validate="many_to_one")
    m["age_years"] = (
        m.age_years + (m.month + pd.offsets.MonthEnd(0) - pd.Timestamp("2025-01-01")).dt.days / 365.25
    )
    m, membership = build_peers(m)
    c = component_comparisons(c, m)
    m["leading_negative_contributor"] = np.where(
        m.peer_health.notna(), "No negative peer contribution", "Peer comparison unavailable"
    )
    for (vid, month), g in c.groupby(["vehicle_id", "month"], sort=True):
        negative = g[g.gap_contribution < -0.05].sort_values(["gap_contribution", "component"])
        if len(negative):
            m.loc[(m.vehicle_id == vid) & m.month.eq(month), "leading_negative_contributor"] = (
                negative.label.iloc[0]
            )
    policy = dict(
        score_version=VERSION,
        simulator_version=SIM_VERSION,
        weights={k: 0.2 for k in SIGNALS},
        mean_weight=0.7,
        tail_weight=0.3,
        percentile="left inverse exposure-weighted empirical CDF: first sorted value with cumulative weight >= 95% total",
        gates=GATES,
        peer=POLICY,
        underperformance_gap=-5,
        bands={
            "90–100": "Small observed deviation",
            "75–<90": "Some observed deviation",
            "0–<75": "Larger observed deviation",
        },
        severe_references={k: s["severe"] for k, s in SIGNALS.items()},
        measurement_validity_bounds=MEASUREMENT_BOUNDS,
        severe_reference_provenance="Fixed synthetic signal perturbation settings chosen in development before evaluation; not manufacturer thresholds",
    )
    tables = {
        "assets": a,
        "observations": obs,
        "vehicle_month_health": m,
        "component_month_health": c,
        "peer_membership": membership,
    }
    for name, f in tables.items():
        f.to_parquet(output / (name + ".parquet"), index=False, compression="zstd")
    truth.to_parquet(evaluation / "simulator_truth.parquet", index=False, compression="zstd")
    events.to_parquet(evaluation / "synthetic_interventions.parquet", index=False, compression="zstd")
    (output / "policy.json").write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n")
    manifest = dict(
        source_revision=FLEETCARE_REF,
        interface_reference_revision=SERVICEPLAN_REF,
        source_blob_sha256=source_hashes or {},
        simulator_version=SIM_VERSION,
        score_version=VERSION,
        seed=20261029,
        month_start="2025-01-01",
        month_end="2025-12-01",
        grain="Daily operating-summary observations weighted by canonical operating hours times recorded fraction",
        counts={n: len(f) for n, f in tables.items()},
        customers=int(a.customer_id.nunique()),
        countries=int(a.country.nunique()),
        models=int(a.model_id.nunique()),
        sha256={
            p.name: sha(p)
            for p in sorted(output.iterdir())
            if p.suffix in [".json", ".parquet"] and p.name != "manifest.json"
        },
        provenance="Canonical identity and usage from pinned FleetCare Git blobs; all condition observations are the separate FleetPulse synthetic extension. No operational databases or service responses were read.",
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fleetcare", type=Path, default=ROOT.parent / "FleetCare-PredictiveMaintenance")
    p.add_argument("--output", type=Path, default=DATA)
    p.add_argument("--evaluation", type=Path, default=EVALUATION)
    args = p.parse_args()
    a, d, h = import_source(args.fleetcare)
    print(json.dumps(build(a, d, args.output, args.evaluation, h), indent=2))


if __name__ == "__main__":
    main()
