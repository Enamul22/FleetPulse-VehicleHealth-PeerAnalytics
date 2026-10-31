import numpy as np
import pandas as pd
import pytest
from fleetpulse.peers import eligible_peers, build_peers
from fleetpulse.config import SIGNALS


def fixture(n=4):
    f = pd.DataFrame(
        dict(
            vehicle_id=[f"T{i}" for i in range(n)],
            month=pd.Timestamp("2025-09-01"),
            model_id="ALD",
            usage_profile="mixed",
            ambient_c=15.0,
            age_years=5.0,
            lifetime_engine_hours=1000.0,
            health=80.0,
            operating_hours=np.arange(n) + 1.0,
        )
    )
    for k in SIGNALS:
        f[k + "_score"] = 80.0
    return f


@pytest.mark.parametrize("n,available,count", [(1, False, 0), (2, False, 1), (3, True, 2)])
def test_minimum_other_distinct_vehicles(n, available, count):
    f = fixture(n)
    out, members = build_peers(f)
    assert out.peer_count.eq(count).all()
    assert out.peer_health.notna().eq(available).all()
    assert not members.vehicle_id.eq(members.peer_id).any()
    assert not members.duplicated(["vehicle_id", "month", "peer_id"]).any()
    if n == 3:
        assert out.peer_support.eq("Limited (2–4 peers)").all()


def test_boundaries_sparse_not_silently_broadened():
    f = fixture(9)
    f.loc[1, ["ambient_c", "age_years", "lifetime_engine_hours"]] = [20.0, 8.0, 1500.0]
    f.loc[2, "ambient_c"] = 20.0 + 1e-8
    f.loc[3, "age_years"] = 8.0 + 1e-8
    f.loc[4, "lifetime_engine_hours"] = 1500.0 + 1e-8
    f.loc[5, "model_id"] = "ELM"
    f.loc[6, "month"] = pd.Timestamp("2025-08-01")
    f.loc[7, "usage_profile"] = "motorway"
    f.loc[8, "health"] = np.nan
    p = eligible_peers(f, f.iloc[0])
    assert p.vehicle_id.tolist() == ["T1"]
    assert pd.isna(build_peers(f)[0].iloc[0].peer_health)
    with pytest.raises(ValueError, match="Duplicate"):
        eligible_peers(pd.concat([f, f.iloc[:1]]), f.iloc[0])
    f = fixture(3)
    f.lifetime_engine_hours = 0.0
    f.loc[1, "lifetime_engine_hours"] = 250.0
    f.loc[2, "lifetime_engine_hours"] = 251.0
    assert eligible_peers(f, f.iloc[0]).vehicle_id.tolist() == ["T1"]


def test_equal_votes_consistent_component_membership_and_no_filter_effect():
    f = fixture(3)
    f.loc[1, "health"] = 20.0
    f.loc[2, "health"] = 100.0
    f.loc[1, "operating_hours"] = 1.0
    f.loc[2, "operating_hours"] = 10000.0
    for k in SIGNALS:
        f.loc[1, k + "_score"] = 20.0
        f.loc[2, k + "_score"] = 100.0
    result, members = build_peers(f)
    assert result.iloc[0].peer_health == 60.0
    assert all(result.iloc[0][k + "_peer"] == 60 for k in SIGNALS)
    assert (
        sum(0.2 * (result.iloc[0][k + "_score"] - result.iloc[0][k + "_peer"]) for k in SIGNALS)
        == result.iloc[0].health_gap
    )
    filtered = result[result.vehicle_id == "T0"].copy()
    assert filtered.peer_health.iloc[0] == 60.0
    # December data does not change September membership/reference.
    future = f.copy()
    future.month = pd.Timestamp("2025-12-01")
    future.ambient_c = 44.0
    future.health = 10.0
    both = pd.concat([f, future], ignore_index=True)
    rebuilt, _ = build_peers(both)
    pd.testing.assert_frame_equal(
        result, rebuilt[rebuilt.month.eq(pd.Timestamp("2025-09-01"))].reset_index(drop=True)
    )
