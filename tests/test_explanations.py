import numpy as np
import pandas as pd
from fleetpulse.config import SIGNALS
from fleetpulse.explanations import explain


def components(own, peer, previous=None):
    rows = []
    for i, (k, s) in enumerate(SIGNALS.items()):
        rows.append(
            dict(
                component=k,
                label=s["label"],
                score=own[i],
                peer_mean=peer[i],
                own_deduction=0.2 * (100 - own[i]),
                gap_contribution=0.2 * (own[i] - peer[i]),
                previous_score=previous[i] if previous else None,
                change_contribution=0.2 * (own[i] - previous[i]) if previous else None,
            )
        )
    return pd.DataFrame(rows)


def test_exact_agreed_fixture_and_positive_offsets():
    c = components([60, 90, 85, 90, 65], [90, 90, 95, 90, 85])
    assert c.score.mean() == 78 and c.peer_mean.mean() == 90
    assert c.own_deduction.sum() == 22
    assert c.gap_contribution.tolist() == [-6, 0, -2, 0, -4]
    assert c.gap_contribution.sum() == -12
    row = dict(
        month=pd.Timestamp("2025-09-01"),
        health=78.0,
        change=np.nan,
        peer_health=90.0,
        health_gap=-12.0,
        peer_count=14,
    )
    out = explain(row, c)
    assert "78.0/100" in out["summary"] and "12.0 points below" in out["summary"]
    assert "previous-month score is unavailable" in out["summary"]
    assert "-6.0 points" in out["contributors"][0]
    # A better component offsets worse ones; negative terms alone are not described as net gap.
    c = components([60, 100, 85, 100, 65], [90, 90, 95, 90, 85])
    out = explain({**row, "health": 82.0, "health_gap": -8.0}, c)
    assert any("Positive offsets" in x and "+2.0" in x for x in out["contributors"])


def test_no_invented_change_comparison_or_diagnosis():
    c = components([95] * 5, [90] * 5)
    row = dict(
        month=pd.Timestamp("2025-01-01"),
        health=95.0,
        change=np.nan,
        peer_health=90.0,
        health_gap=5.0,
        peer_count=2,
    )
    out = explain(row, c)
    assert "5.0 points above" in out["summary"] and "limited comparison" in out["summary"]
    assert not any("negative peer-gap" in x for x in out["contributors"])
    absent = explain(
        {**row, "peer_health": np.nan, "health_gap": np.nan, "peer_count": 1},
        c.assign(peer_mean=np.nan, gap_contribution=np.nan),
    )
    assert "1 other eligible" in absent["summary"] and not any(
        "peer-gap" in x for x in absent["contributors"]
    )
    missing = explain({**row, "health": np.nan, "data_status": "Less than 80% valid exposure"}, c)
    assert "unavailable" in missing["summary"] and "not reweighted" in missing["summary"]
    assert not missing["contributors"]
