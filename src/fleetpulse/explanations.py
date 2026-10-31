"""Deterministic evidence templates. Contributions describe arithmetic, not causation."""

import pandas as pd
from .config import SIGNALS


def band(score):
    if pd.isna(score):
        return "Overall score unavailable"
    return (
        "Small observed deviation"
        if score >= 90
        else "Some observed deviation"
        if score >= 75
        else "Larger observed deviation"
    )


def explain(row, components):
    month = pd.Timestamp(row["month"]).strftime("%B %Y")
    health = row["health"]
    sentences = []
    if pd.isna(health):
        sentences.append(
            f"{month}: the overall health index is unavailable. {row['data_status']}. Available component readings remain visible; missing channels are not reweighted."
        )
        return dict(
            summary=" ".join(sentences),
            contributors=[],
            investigations=["Restore sufficient supported measurements before making an overall comparison."],
            caveat="Coverage describes recorded operating exposure, not a confidence probability.",
        )
    sentences.append(
        f"{month} health is {health:.1f}/100: {band(health).lower()} from the frozen healthy-context reference."
    )
    change = row["change"]
    if pd.isna(change):
        sentences.append("A comparable previous-month score is unavailable; no monthly change is inferred.")
    elif abs(change) < 0.05:
        sentences.append("The index is within 0.1 points of the previous month.")
    else:
        sentences.append(
            f"The index {'rose' if change > 0 else 'fell'} {abs(change):.1f} points from the previous month."
        )
    if pd.isna(row["peer_health"]):
        sentences.append(
            f"Peer comparison is unavailable: {int(row['peer_count'])} other eligible vehicles; at least two are required. The vehicle's own index stands independently."
        )
    else:
        gap = row["health_gap"]
        n = int(row["peer_count"])
        if abs(gap) < 0.05:
            sentences.append(f"It is within 0.1 points of the mean of {n} matched vehicles.")
        else:
            sentences.append(
                f"It is {abs(gap):.1f} points {'below' if gap < 0 else 'above'} the {row['peer_health']:.1f}/100 average of {n} matched vehicles."
            )
        if n <= 4:
            sentences.append(
                "This is a limited comparison group of two to four peers, not a statistical significance claim."
            )
    neg = components[components.gap_contribution < -0.05].sort_values("gap_contribution")
    pos = components[components.gap_contribution > 0.05].sort_values("gap_contribution", ascending=False)
    contributors = []
    if len(neg):
        contributors.append(
            "Largest negative peer-gap contributions: "
            + ", ".join(f"{r.label}: {r.gap_contribution:.1f} points" for r in neg.head(3).itertuples())
            + "."
        )
    if len(pos):
        contributors.append(
            "Positive offsets: "
            + ", ".join(f"{r.label}: +{r.gap_contribution:.1f} points" for r in pos.itertuples())
            + "."
        )
    own = components[components.own_deduction > 0.05].sort_values("own_deduction", ascending=False)
    if len(own):
        contributors.append(
            f"Reduction from 100: {100 - health:.1f} points across all five indicators. Largest own deductions: "
            + ", ".join(f"{r.label}: {r.own_deduction:.1f}" for r in own.head(2).itertuples())
            + "."
        )
    suggestions = [
        SIGNALS[str(r.component)]["investigate"] for r in own[own.own_deduction > 0.4].head(3).itertuples()
    ]
    if not suggestions:
        suggestions = [
            "Continue reviewing measurement coverage and context; the available data shows only small deviations from the healthy reference."
        ]
    return dict(
        summary=" ".join(sentences),
        contributors=contributors,
        investigations=suggestions,
        caveat="These indicators contribute to the score difference; they do not establish a faulty part. Monthly matched peers can change. Daily tail statistics describe operating summaries, not intraday peaks.",
    )
