import hashlib, os, subprocess, sys
import numpy as np
import pandas as pd
import pytest
from fleetpulse.config import DATA, ROOT
from fleetpulse.reporting import load_data, overview, filter_rows, page_slice, trend, detail
from fleetpulse.scoring import score_months


@pytest.fixture(scope="module")
def bundle():
    return load_data()


def test_complete_grid_keys_source_counters_and_checksums(bundle):
    m = bundle["vehicle_month_health"]
    c = bundle["component_month_health"]
    a = bundle["assets"]
    assert len(m) == 12000 and not m.duplicated(["vehicle_id", "month"]).any()
    assert len(c) == 60000 and not c.duplicated(["vehicle_id", "month", "component"]).any()
    assert (
        len(a) == 1000
        and a.customer_id.nunique() == 201
        and a.model_id.nunique() == 4
        and a.country.nunique() == 4
    )
    assert all(len(overview(bundle, month)) == 1000 for month in m.month.unique())
    assert m.health.isna().any() and m.health.dropna().between(0, 100).all()
    for name, sha in bundle["manifest"]["sha256"].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == sha
    obs = pd.read_parquet(DATA / "observations.parquet")
    assert len(obs) == 365000 and obs.groupby("vehicle_id").size().eq(365).all()
    assert not obs.duplicated(["vehicle_id", "date"]).any()
    assert not any("hidden" in col or "intervention" in col for col in obs.columns)
    sums = obs.groupby("vehicle_id").agg(
        hours=("operating_hours", "sum"),
        distance=("distance_km", "sum"),
        end_km=("odometer_km", "last"),
        end_hours=("lifetime_engine_hours", "last"),
    )
    initial = a.set_index("vehicle_id")
    np.testing.assert_allclose(sums.end_km - initial.initial_odometer_km, sums.distance, atol=1e-7)
    np.testing.assert_allclose(sums.end_hours - initial.initial_engine_hours, sums.hours, atol=1e-7)
    # Replay observed features for a genuine vehicle and compare to saved scores.
    selected = obs[obs.vehicle_id == "VEH-0001"]
    rebuilt, _ = score_months(selected, bundle["baseline"])
    pd.testing.assert_series_equal(
        rebuilt.health.reset_index(drop=True),
        m[m.vehicle_id == "VEH-0001"].health.reset_index(drop=True),
        check_names=False,
    )


def test_exact_contributions_and_membership(bundle):
    m = bundle["vehicle_month_health"].set_index(["vehicle_id", "month"])
    c = bundle["component_month_health"]
    p = bundle["peer_membership"]
    own = c.groupby(["vehicle_id", "month"]).own_deduction.sum(min_count=5)
    gap = c.groupby(["vehicle_id", "month"]).gap_contribution.sum(min_count=5)
    change = c.groupby(["vehicle_id", "month"]).change_contribution.sum(min_count=5)
    np.testing.assert_allclose(own, m.health.rsub(100).reindex(own.index), atol=1e-10, equal_nan=True)
    np.testing.assert_allclose(gap, m.health_gap.reindex(gap.index), atol=1e-10, equal_nan=True)
    np.testing.assert_allclose(change, m.change.reindex(change.index), atol=1e-10, equal_nan=True)
    assert not p.vehicle_id.eq(p.peer_id).any() and not p.duplicated(["vehicle_id", "month", "peer_id"]).any()
    assert (p.ambient_difference_c <= 5 + 1e-12).all() and (p.age_difference_years <= 3 + 1e-12).all()
    assert (p.hours_difference <= p.hours_limit + 1e-12).all()
    counts = p.groupby(["vehicle_id", "month"]).peer_id.nunique()
    pd.testing.assert_series_equal(counts, m.peer_count.reindex(counts.index), check_names=False)
    assert m.loc[m.peer_count.lt(2), "peer_health"].isna().all()
    target = m[m.peer_count.ge(5)].iloc[0]
    vid, month = target.name
    members = p[p.vehicle_id.eq(vid) & p.month.eq(month)].peer_id
    assert target.peer_health == pytest.approx(m.loc[(members.tolist(), month), "health"].mean())


def test_full_filter_page_download_and_frozen_reference(bundle):
    f = overview(bundle, "2025-12-01")
    original = f.copy(deep=True)
    filtered = filter_rows(f, {"country": "Finland", "sort": "Vehicle ID"})
    assert len(filtered) > 25
    pages = [page_slice(filtered, i, 25)[0] for i in range(1, int(np.ceil(len(filtered) / 25)) + 1)]
    pd.testing.assert_frame_equal(pd.concat(pages), filtered)
    csv = pd.read_csv(__import__("io").StringIO(filtered.to_csv(index=False)))
    assert len(csv) == len(filtered) and csv.vehicle_id.is_unique
    pd.testing.assert_frame_equal(f, original)
    row = filtered.iloc[0]
    r, _, _ = detail(bundle, row.vehicle_id, row.month)
    assert r["peer_health"] == row.peer_health or (pd.isna(r["peer_health"]) and pd.isna(row.peer_health))
    assert filter_rows(f, {"search": "[.*"}).empty  # Literal search, not regex execution.
    nulls = filter_rows(f, {"band": "Unavailable"})
    assert len(nulls) == f.health.isna().sum()
    assert not filter_rows(f, {"underperformance": True}).health_gap.gt(-5).any()


def test_trend_uses_selected_and_previous_three_months(bundle):
    t = trend(bundle, "VEH-0001", "2025-09-01")
    assert t.month.dt.strftime("%Y-%m").tolist() == ["2025-06", "2025-07", "2025-08", "2025-09"]
    assert len(trend(bundle, "VEH-0001", "2025-01-01")) == 1
    assert len(trend(bundle, "VEH-0001", "2025-02-01")) == 2
    # An unavailable score remains a gap, not interpolated or replaced with zero.
    m = bundle["vehicle_month_health"]
    missing = m[m.health.isna()].iloc[0]
    assert pd.isna(trend(bundle, missing.vehicle_id, missing.month).health.iloc[-1])


def test_generator_calibration_reproducible_across_processes_hash_seeds(tmp_path, bundle):
    a = bundle["assets"].head(2)
    d = pd.read_parquet(DATA / "observations.parquet")
    d = d[d.vehicle_id.isin(a.vehicle_id)][
        ["vehicle_id", "date", "operating_hours", "distance_km", "odometer_km", "lifetime_engine_hours"]
    ].copy()
    a.to_parquet(tmp_path / "assets.parquet", index=False)
    d.to_parquet(tmp_path / "usage.parquet", index=False)
    script = """import json,sys,hashlib,pandas as pd
from pathlib import Path
from fleetpulse.simulation import extend
from fleetpulse.baseline import calibrate
p=Path(sys.argv[1]);a=pd.read_parquet(p/'assets.parquet');d=pd.read_parquet(p/'usage.parquet');o,t,e=extend(a,d)
x=[hashlib.sha256(pd.util.hash_pandas_object(f,index=False).values.tobytes()).hexdigest() for f in [o,t,e]]
x.append(hashlib.sha256(json.dumps(calibrate(),sort_keys=True).encode()).hexdigest());print(json.dumps(x))"""
    results = []
    for seed in ["17", "923"]:
        e = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONHASHSEED=seed, OPENBLAS_NUM_THREADS="1")
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)], env=e, capture_output=True, text=True, timeout=90
        )
        assert result.returncode == 0, result.stderr
        results.append(result.stdout)
    assert results[0] == results[1]
