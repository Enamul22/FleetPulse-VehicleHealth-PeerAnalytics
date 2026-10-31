"""Read-only month -> overview -> detail. All inference and matching are offline."""

import math, hashlib
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from .config import DATA, MODELS
from .reporting import load_data, overview, filter_rows, page_slice, trend, detail
from .explanations import explain

LABELS = {
    "vehicle_id": "Vehicle ID",
    "vehicle_name": "Vehicle name",
    "model_id": "Model",
    "country": "Country",
    "city": "City",
    "usage_profile": "Usage profile",
    "health": "Health /100",
    "change": "Monthly change",
    "peer_health": "Peer mean /100",
    "health_gap": "Gap (points)",
    "peer_count": "Other peers",
    "coverage": "Valid exposure",
    "data_status": "Data status",
    "leading_negative_contributor": "Leading negative contributor",
    "age_years": "Age (years)",
    "odometer_km": "Odometer (km)",
    "lifetime_engine_hours": "Lifetime hours",
    "operating_hours": "Month hours",
    "distance_km": "Month distance (km)",
    "ambient_c": "Ambient (°C)",
    "customer_name": "Customer",
    "month": "Month",
}


@st.cache_data(show_spinner=False)
def prepared(bundle_fingerprint):
    return load_data(DATA)


def display(f, columns):
    out = f.reindex(columns=columns).copy()
    if "month" in out:
        out["month"] = out.month.dt.strftime("%Y-%m")
    if "coverage" in out:
        out["coverage"] = (out.coverage * 100).round(1)
    if "model_id" in out:
        out["model_id"] = out.model_id.map(MODELS)
    return out.rename(columns=LABELS)


def main():
    st.set_page_config(
        page_title="FleetPulse · Vehicle Health & Peer Analytics", page_icon="◉", layout="wide"
    )
    st.markdown(
        """<style>.block-container{padding-top:2.5rem;max-width:1650px}h1{letter-spacing:-1px}.eyebrow{color:#147d92;font-size:12px;font-weight:700;letter-spacing:2px}[data-testid="stMetric"]{background:white;border:1px solid #dce5ea;padding:10px;border-radius:8px}@media(max-width:650px){.block-container{padding-top:3rem;padding-left:1rem;padding-right:1rem}[data-testid="stHorizontalBlock"]{flex-wrap:wrap}[data-testid="stColumn"]{min-width:100%!important}}</style>""",
        unsafe_allow_html=True,
    )
    try:
        b = prepared(hashlib.sha256((DATA / "manifest.json").read_bytes()).hexdigest())
    except (ValueError, OSError) as exc:
        st.error("Cannot read the complete prepared FleetPulse data bundle. " + str(exc))
        st.stop()
    months = sorted(b["vehicle_month_health"].month.unique())
    with st.sidebar:
        st.markdown("### ◉ FleetPulse")
        st.caption("VEHICLE HEALTH & PEER ANALYTICS")
        month = st.selectbox(
            "Analysis month",
            months,
            index=len(months) - 1,
            format_func=lambda x: pd.Timestamp(x).strftime("%B %Y"),
            key="fp_month",
        )
        st.caption("One shared month controls scores, comparisons and explanations.")
        st.divider()
        st.markdown("**Read-only portfolio demonstration**")
        st.caption(
            "The index summarises measured deviations in fictional daily operating summaries. It is not remaining life or a failure probability."
        )
        st.caption("Enamul Haque · 1,000 fictional vehicles · 2025")
        with st.expander("Score & reference policy"):
            st.write(
                "Five equal 20% indicators. 70% exposure-weighted mean severity + 30% exposure-weighted 95th percentile."
            )
            st.write(
                "At least 80% valid operating exposure, five active days and ten supported hours for every indicator. Two other valid peers minimum."
            )
            st.caption(b["manifest"]["score_version"] + " / " + b["policy"]["peer"]["version"])
    month = pd.Timestamp(month)
    if st.session_state.get("fp_context_month") != month:
        st.session_state.fp_context_month = month
        st.session_state.fp_page = 1
        st.session_state.fp_epoch = st.session_state.get("fp_epoch", 0) + 1
    st.markdown('<div class="eyebrow">FLEETPULSE / CONDITION & COMPARISON</div>', unsafe_allow_html=True)
    if st.session_state.get("fp_selected"):
        vehicle_detail(b, st.session_state.fp_selected, month)
    else:
        fleet_overview(b, month)


def fleet_overview(b, month):
    st.title("Fleet overview")
    st.write(
        "Understand each vehicle’s condition, then compare it with vehicles operating in similar conditions."
    )
    f = overview(b, month)
    saved = st.session_state.get("fp_filters", {})
    filters = {}
    cols = st.columns([2, 1, 1])
    filters["search"] = cols[0].text_input(
        "Search vehicle, name, customer or city", value=saved.get("search", ""), key="fp_search"
    )
    for col, key, label in [(cols[1], "model_id", "Model / type"), (cols[2], "country", "Country")]:
        opts = ["All"] + sorted(f[key].unique())
        old = saved.get(key, "All")
        filters[key] = col.selectbox(
            label, opts, index=opts.index(old), format_func=lambda x: MODELS.get(x, x), key="fp_" + key
        )
    with st.expander("More filters and sorting"):
        cols = st.columns(3)
        for col, key, label, opts in [
            (cols[0], "usage_profile", "Usage profile", ["All"] + sorted(f.usage_profile.unique())),
            (cols[1], "band", "Index band", ["All", "90–100", "75–<90", "0–<75", "Unavailable"]),
            (cols[2], "peers", "Peer availability", ["All", "Available", "Limited (2–4)", "Unavailable"]),
        ]:
            filters[key] = col.selectbox(
                label, opts, index=opts.index(saved.get(key, opts[0])), key="fp_" + key
            )
        filters["underperformance"] = st.checkbox(
            "At least 5 points below matched peers",
            value=saved.get("underperformance", False),
            key="fp_underperformance",
        )
        filters["use_range"] = st.checkbox(
            "Filter score range", value=saved.get("use_range", False), key="fp_use_range"
        )
        if filters["use_range"]:
            filters["range"] = st.slider(
                "Health index range", 0, 100, value=tuple(saved.get("range", (0, 100))), key="fp_range"
            )
            filters["include_unavailable"] = st.checkbox(
                "Include unavailable scores",
                value=saved.get("include_unavailable", True),
                key="fp_include_unavailable",
            )
        sorts = [
            "Health · lowest first",
            "Health · highest first",
            "Peer gap · lowest first",
            "Vehicle ID",
            "Change · lowest first",
        ]
        filters["sort"] = st.selectbox(
            "Sort", sorts, index=sorts.index(saved.get("sort", sorts[0])), key="fp_sort"
        )
        st.caption(
            "Bands and the 5-point filter are demonstration categories, not safety classifications. Filters never change scores or the reference cohort."
        )
    if filters != saved:
        st.session_state.fp_page = 1
        st.session_state.fp_epoch = st.session_state.get("fp_epoch", 0) + 1
    st.session_state.fp_filters = filters
    filtered = filter_rows(f, filters)
    cols = st.columns(4)
    cols[0].metric("Vehicles in month", f"{len(f):,}")
    cols[1].metric("Matching vehicles", f"{len(filtered):,}")
    cols[2].metric("With own index", f"{f.health.notna().sum():,}")
    cols[3].metric("With peer comparison", f"{f.peer_health.notna().sum():,}")
    st.caption(
        f"{month:%B %Y} · {b['manifest']['customers']} customers · all 1,000 assets retained before filters. Select a row to inspect its evidence."
    )
    controls = st.columns([1, 1.2, 1])
    extra = controls[0].checkbox("More columns", key="fp_extra")
    controls[1].download_button(
        "Download all filtered vehicles",
        filtered.to_csv(index=False).encode(),
        file_name=f"fleetpulse-{month:%Y-%m}.csv",
        mime="text/csv",
    )
    if filtered.empty:
        st.info(
            "No vehicles match these filters. Broaden the selection to include unavailable scores or other models."
        )
        return
    max_page = max(1, math.ceil(len(filtered) / 25))
    page = controls[2].number_input(
        "Page",
        label_visibility="collapsed",
        min_value=1,
        max_value=max_page,
        value=min(st.session_state.get("fp_page", 1), max_page),
        step=1,
        key="fp_page_" + str(st.session_state.get("fp_epoch", 0)),
    )
    st.session_state.fp_page = page
    visible, _, count = page_slice(filtered, page)
    st.caption(f"{len(filtered):,} matching / {len(f):,} total · page {page} of {count}")
    columns = [
        "vehicle_id",
        "model_id",
        "country",
        "health",
        "change",
        "peer_health",
        "health_gap",
        "peer_count",
        "coverage",
        "data_status",
    ]
    if extra:
        columns += [
            "vehicle_name",
            "city",
            "month",
            "age_years",
            "odometer_km",
            "lifetime_engine_hours",
            "operating_hours",
            "distance_km",
            "leading_negative_contributor",
        ]
    event = st.dataframe(
        display(visible, columns),
        hide_index=True,
        width="stretch",
        height=410,
        on_select="rerun",
        selection_mode="single-row",
        key="fp_rows_" + str(st.session_state.get("fp_epoch", 0)),
        column_config={
            "Health /100": st.column_config.NumberColumn(format="%.1f"),
            "Peer mean /100": st.column_config.NumberColumn(format="%.1f"),
            "Gap (points)": st.column_config.NumberColumn(format="%+.1f"),
            "Monthly change": st.column_config.NumberColumn(format="%+.1f"),
            "Valid exposure": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    if event.selection.rows:
        st.session_state.fp_selected = visible.iloc[event.selection.rows[0]].vehicle_id
        st.rerun()


def gauge(value, title):
    if pd.isna(value):
        st.markdown("**" + title + "**")
        st.info("Unavailable")
        return
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"size": 15}},
            number={"suffix": " /100", "valueformat": ".1f", "font": {"size": 25}},
            gauge={
                "axis": {"range": [0, 100], "tickvals": [0, 50, 100]},
                "bar": {"color": "#147d92"},
                "bgcolor": "#e3e9ed",
                "borderwidth": 0,
            },
        )
    )
    fig.update_layout(height=200, margin=dict(t=35, b=10, l=24, r=24))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def trend_chart(f):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=f.month,
            y=f.health,
            name="Vehicle health",
            mode="lines+markers",
            connectgaps=False,
            line={"color": "#147d92", "width": 3},
        )
    )
    if f.peer_health.notna().any():
        fig.add_trace(
            go.Scatter(
                x=f.month,
                y=f.peer_health,
                name="Monthly matched-peer average",
                mode="lines+markers",
                connectgaps=False,
                line={"color": "#b28238", "dash": "dash"},
                customdata=f.peer_count,
                hovertemplate="%{y:.1f}/100 · %{customdata} other peers<extra></extra>",
            )
        )
    fig.update_layout(
        height=275,
        yaxis={"range": [0, 100], "title": "Condition index /100"},
        xaxis={"tickformat": "%b %Y", "tickvals": f.month},
        margin=dict(t=10, b=15, l=10, r=10),
        legend={"orientation": "h", "y": 1.2},
    )
    return fig


def vehicle_detail(b, vehicle, month):
    if st.button("← Back to fleet overview"):
        st.session_state.pop("fp_selected", None)
        st.session_state.fp_epoch = st.session_state.get("fp_epoch", 0) + 1
        st.rerun()
    row, c, members = detail(b, vehicle, month)
    st.title(f"{vehicle} · {MODELS[row['model_id']]}")
    st.caption(
        f"{row['vehicle_type']} · {row['city']}, {row['country']} · {row['customer_name']} ({row['customer_id']}) · {row['usage_profile']} usage · {month:%B %Y}"
    )
    cols = st.columns(5)
    for col, label, value in zip(
        cols,
        ["Age (years)", "Odometer (km)", "Lifetime hours (h)", "Month hours (h)", "Month distance (km)"],
        [
            f"{row['age_years']:.1f}",
            f"{row['odometer_km']:,.0f}",
            f"{row['lifetime_engine_hours']:,.1f}",
            f"{row['operating_hours']:,.1f}",
            f"{row['distance_km']:,.0f}",
        ],
    ):
        col.metric(label, value)
    st.caption(
        f"Valid operating exposure: {row['coverage']:.1%} minimum across all five indicators · {row['active_days']} active source days · {row['data_status']}."
    )
    if c.unsupported_hours.max() > 0:
        st.warning(
            f"{c.unsupported_hours.max():.1f} operating hours were outside the healthy-context reference and excluded. Inspect the exposure table before comparing results."
        )
    st.subheader("Health & recent trend")
    cols = st.columns([1, 1, 2.4])
    with cols[0]:
        gauge(row["health"], "Vehicle health")
    with cols[1]:
        gauge(row["peer_health"], "Peer-average health")
    with cols[2]:
        st.plotly_chart(trend_chart(trend(b, vehicle, month)), use_container_width=True)
    if pd.notna(row["health_gap"]):
        st.write(
            f"**Peer gap: {row['health_gap']:+.1f} points** · {int(row['peer_count'])} other vehicles · {row['peer_support']}"
        )
    else:
        st.info(
            f"Peer comparison unavailable · {int(row['peer_count'])} other eligible vehicles. {row['peer_reason']}."
        )
    st.caption(
        "Trend shows this month and up to three preceding months. Gaps are missing evidence; each peer average uses that month’s matching membership."
    )
    st.subheader("Matched-peer comparison")
    st.caption(
        "Same model, month and usage profile; observed ambient within 5 °C, age within 3 years, lifetime hours within 50% of the target (500-hour denominator floor). Every qualifying peer has one equal vote; two others minimum."
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(y=c.label, x=c.score, name="Vehicle", orientation="h", marker_color="#147d92"))
    if pd.notna(row["peer_health"]):
        fig.add_trace(
            go.Bar(y=c.label, x=c.peer_mean, name="Peer average", orientation="h", marker_color="#b28238")
        )
    fig.update_layout(
        barmode="group",
        height=300,
        xaxis={"range": [0, 100], "title": "Component index /100"},
        yaxis={"autorange": "reversed"},
        margin=dict(t=10, b=10, l=5, r=5),
        legend={"orientation": "h", "y": 1.15},
    )
    st.plotly_chart(fig, use_container_width=True)
    evidence = c[
        [
            "label",
            "unit",
            "observed_mean",
            "expected_mean",
            "adverse_mean",
            "score",
            "peer_mean",
            "coverage",
            "active_days",
            "valid_hours",
            "status",
        ]
    ].rename(
        columns={
            "label": "Indicator",
            "unit": "Unit",
            "observed_mean": "Observed daily mean",
            "expected_mean": "Expected at own context",
            "adverse_mean": "Adverse residual mean",
            "score": "Vehicle /100",
            "peer_mean": "Peer /100",
            "coverage": "Valid exposure fraction",
            "active_days": "Valid active days",
            "valid_hours": "Valid operating hours",
            "status": "Evidence status",
        }
    )
    st.dataframe(evidence.round(3), hide_index=True, width="stretch")
    with st.expander("Exposure denominators, quality and aggregation"):
        st.dataframe(
            c[
                [
                    "label",
                    "total_hours",
                    "valid_hours",
                    "unrecorded_hours",
                    "unsupported_hours",
                    "invalid_sensor_hours",
                    "active_days",
                    "coverage",
                    "mean_severity",
                    "tail95_severity",
                    "burden",
                ]
            ].round(4),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "The denominator is known canonical operating exposure. Valid hours exclude recorder gaps, unsupported contexts and invalid sensors. The 95th percentile is the left inverse weighted empirical CDF; these are daily operating summaries."
        )
    st.caption(
        "Signal means use eligible recorded exposure. Expected values adjust for observable model, ambient, load and RPM. Peer component scores use the same members as the overall peer mean; raw temperatures alone do not establish underperformance."
    )
    with st.expander(f"Inspect matched vehicles ({len(members)} candidates)"):
        if members.empty:
            st.write("No eligible comparator meets the frozen criteria. Criteria are not relaxed.")
        else:
            st.dataframe(
                members[
                    [
                        "peer_id",
                        "country",
                        "age_years",
                        "lifetime_engine_hours",
                        "ambient_c",
                        "health",
                        "ambient_difference_c",
                        "age_difference_years",
                        "hours_difference",
                        "hours_limit",
                    ]
                ].round(3),
                hide_index=True,
                width="stretch",
            )
    st.subheader("Overall interpretation")
    result = explain(row, c)
    st.write(result["summary"])
    for text in result["contributors"]:
        st.write(text)
    st.markdown("**Suggested investigations**")
    for text in result["investigations"]:
        st.write("• " + text)
    st.caption(result["caveat"])
    with st.expander("Trace score arithmetic and evidence"):
        st.dataframe(
            c[
                [
                    "label",
                    "score",
                    "own_deduction",
                    "peer_mean",
                    "gap_contribution",
                    "previous_score",
                    "change_contribution",
                ]
            ]
            .rename(
                columns={
                    "label": "Indicator",
                    "score": "Own component",
                    "own_deduction": "Deduction from 100",
                    "peer_mean": "Peer component",
                    "gap_contribution": "Peer-gap contribution",
                    "previous_score": "Previous component",
                    "change_contribution": "Monthly-change contribution",
                }
            )
            .round(4),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Each contribution has weight 0.20. Own deductions sum to 100 − health; peer contributions sum to own − peer mean. Monthly-change contributions reconstruct the change only when both complete overall scores exist. Calculations precede rounding."
        )
        baseline = b["baseline"]
        st.json(
            {
                "score_version": baseline["version"],
                "reference_version": b["policy"]["peer"]["version"],
                "healthy_tolerances": {k: v["healthy_tolerance"] for k, v in baseline["signals"].items()},
                "source_revision": b["manifest"]["source_revision"],
            }
        )
