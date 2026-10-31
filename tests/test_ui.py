import json
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from fleetpulse.config import ROOT
from fleetpulse.reporting import load_data


def charts(app):
    return [json.loads(x.proto.spec) for x in app.get("plotly_chart")]


def test_overview_back_filters_page_month_and_chart_agreement(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@do-not-connect.invalid/unused")
    monkeypatch.setenv("SERVICEPLAN_DATABASE_URL", "unused")
    at = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert not at.exception and not at.error and not at.get("form")
    assert pd.Timestamp(at.selectbox(key="fp_month").value) == pd.Timestamp("2025-12-01")
    assert at.metric[0].value == "1,000" and len(at.dataframe[0].value) == 25
    at.selectbox(key="fp_model_id").select("ALD")
    at.selectbox(key="fp_sort").select("Vehicle ID")
    at.run()
    next(x for x in at.number_input if x.label == "Page").set_value(3).run()
    visible = at.dataframe[0].value.copy()
    vid = visible["Vehicle ID"].iloc[0]
    saved = dict(at.session_state["fp_filters"])
    at.session_state["fp_selected"] = vid
    at.run()
    assert not at.exception and vid in at.title[0].value
    figures = charts(at)
    gauges = [f for f in figures if f["data"][0]["type"] == "indicator"]
    row = (
        load_data()["vehicle_month_health"]
        .query("vehicle_id==@vid")
        .set_index("month")
        .loc[pd.Timestamp("2025-12-01")]
    )
    assert gauges[0]["data"][0]["value"] == pytest.approx(row.health)
    assert gauges[1]["data"][0]["value"] == pytest.approx(row.peer_health)
    next(b for b in at.button if b.label == "← Back to fleet overview").click().run()
    assert not at.exception and at.session_state["fp_filters"] == saved
    assert next(x for x in at.number_input if x.label == "Page").value == 3
    pd.testing.assert_frame_equal(visible, at.dataframe[0].value)
    at.session_state["fp_selected"] = vid
    at.run()
    at.selectbox(key="fp_month").set_value(pd.Timestamp("2025-09-01")).run()
    assert not at.exception and vid in at.title[0].value
    trend = next(f for f in charts(at) if f["data"][0]["type"] == "scatter")
    dates = pd.to_datetime(trend["data"][0]["x"])
    assert dates.min() == pd.Timestamp("2025-06-01") and dates.max() == pd.Timestamp("2025-09-01")
    next(b for b in at.button if b.label == "← Back to fleet overview").click().run()
    assert not at.exception and pd.Timestamp(at.selectbox(key="fp_month").value) == pd.Timestamp("2025-09-01")


@pytest.mark.parametrize(
    "kind", ["healthy", "declining", "rebounded", "missing", "no_peers", "one_peer", "limited"]
)
def test_detail_available_unavailable_and_narratives(kind):
    report = json.loads((ROOT / "data/evaluation/validation.json").read_text())
    vid = report["examples"][kind]
    assert vid is not None
    at = AppTest.from_file(ROOT / "app.py", default_timeout=30)
    at.session_state["fp_selected"] = vid
    at.run()
    assert not at.exception and not at.error
    assert any(x.value == "Overall interpretation" for x in at.subheader)
    gs = [f for f in charts(at) if f["data"][0]["type"] == "indicator"]
    if kind == "missing":
        assert len(gs) == 0
    elif kind in ["no_peers", "one_peer"]:
        assert len(gs) == 1
    else:
        m = load_data()["vehicle_month_health"]
        row = m[m.vehicle_id.eq(vid) & m.month.eq(pd.Timestamp("2025-12-01"))].iloc[0]
        assert len(gs) == int(pd.notna(row.health)) + int(pd.notna(row.peer_health))
    text = " ".join(m.value for m in at.markdown)
    if kind in ["missing", "no_peers", "one_peer"]:
        assert "unavailable" in text.lower()
    assert not any(b.label in ["Sign in", "Create work order", "Submit response"] for b in at.button)
