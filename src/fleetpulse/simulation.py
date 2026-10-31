"""Offline observation-first synthetic extension. Hidden labels never enter scoring."""

import hashlib
import numpy as np
import pandas as pd
from .baseline import healthy_expectation
from .config import SIGNALS, SIM_VERSION


def rng_for(key, seed=20261029):
    return np.random.default_rng(int.from_bytes(hashlib.sha256(f"{seed}|{key}".encode()).digest()[:8], "big"))


def extend(assets, usage):
    frames = []
    truth = []
    events = []
    for a in assets.sort_values("vehicle_id").itertuples():
        f = usage[usage.vehicle_id == a.vehicle_id].sort_values("date").copy().reset_index(drop=True)
        rng = rng_for(a.vehicle_id)
        n = len(f)
        t = np.arange(n)
        f["date"] = pd.to_datetime(f.date, utc=True).dt.tz_localize(None)
        f["month"] = f.date.dt.to_period("M").dt.to_timestamp()
        f["model_id"] = a.model_id
        city_shift = (int(hashlib.sha256(a.city.encode()).hexdigest()[:6], 16) % 100) / 50 - 1
        climate = {"Finland": -4.0, "Germany": 3.0, "United Kingdom": 1.0, "Spain": 7.0}.get(a.country, 0.0)
        season = 10 + 14 * np.sin(2 * np.pi * (f.date.dt.dayofyear.to_numpy() - 110) / 365)
        weather = np.zeros(n)
        for d in range(1, n):
            weather[d] = 0.8 * weather[d - 1] + rng.normal(0, 1.2)
        f["ambient_c"] = season + climate + city_shift + weather
        profile = {"urban": 0.43, "mixed": 0.52, "motorway": 0.64}.get(a.usage_profile, 0.5)
        f["load"] = np.clip(profile + rng.normal(0, 0.07, n) + rng.normal(0, 0.03), 0.12, 0.91)
        f["rpm"] = np.clip(1100 + 1900 * f.load + rng.normal(0, 130, n), 850, 3800)
        f["charging_expected"] = f.operating_hours > 0
        f["recorded_fraction"] = rng.uniform(0.94, 1.0, n)
        # Independent recorder outages preserve canonical usage/counters; no false zero-driving claim.
        outages = {m: bool(rng.random() < 0.012) for m in range(1, 13)}
        f.loc[f.date.dt.month.map(outages), "recorded_fraction"] = 0.0
        # Some entire months are outside the frozen reference's ambient support.
        unsupported = {m: bool(rng.random() < 0.004) for m in range(1, 13)}
        f.loc[f.date.dt.month.map(unsupported), "ambient_c"] = 49.0 + rng.uniform(0, 3)
        for col, decimals in {"ambient_c": 2, "load": 4, "rpm": 1, "recorded_fraction": 4}.items():
            f[col] = f[col].round(decimals).astype("float32")
        expected = healthy_expectation(f)
        for k, s in SIGNALS.items():
            base = rng.beta(0.8, 6) * 0.65
            drift = rng.uniform(0, 0.0005)
            start = int(rng.integers(50, 260))
            accel = rng.uniform(0.0003, 0.003) if rng.random() < 0.38 else 0.0
            latent = np.clip(base + drift * t + accel * np.maximum(t - start, 0), 0, 1.3)
            intervention = int(rng.integers(190, 330)) if rng.random() < 0.18 else None
            if intervention is not None and intervention < n:
                latent[intervention:] = np.maximum(0.015, latent[intervention:] - latent[intervention] * 0.75)
                events.append(
                    dict(
                        vehicle_id=a.vehicle_id,
                        component=k,
                        date=f.date.iloc[intervention],
                        source=SIM_VERSION + "-synthetic-intervention",
                    )
                )
            noise = np.zeros(n)
            for d in range(n):
                noise[d] = (0.35 * noise[d - 1] if d else 0) + rng.normal(0, s["noise"])
            offset = rng.normal(0, 0.15 * s["noise"])
            observed = expected[k] + s["direction"] * s["severe"] * latent + noise + offset
            valid = rng.random(n) > 0.009
            missing = {m: bool(rng.random() < 0.016) for m in range(1, 13)}
            valid &= ~f.date.dt.month.map(missing).to_numpy()
            observed[~valid] = np.nan
            # Explicit quality flag, not condition deduction, for implausible sensor values.
            bad = rng.random(n) < 0.002
            observed[bad] = 9999.0
            valid[bad] = False
            if k == "lubrication":
                observed = np.maximum(observed, 0.02)
            f[s["signal"]] = np.round(observed, 2 if k in ["oil", "cooling"] else 3).astype("float32")
            f[k + "_valid"] = valid
            tr = pd.DataFrame(
                dict(
                    vehicle_id=a.vehicle_id,
                    month=f.month,
                    component=k,
                    hidden_loss=latent,
                    operating_hours=f.operating_hours,
                )
            )
            for month, g in tr.groupby("month", sort=True):
                truth.append(
                    dict(
                        vehicle_id=a.vehicle_id,
                        month=month,
                        component=k,
                        hidden_loss=float(np.average(g.hidden_loss, weights=g.operating_hours))
                        if g.operating_hours.sum() > 0
                        else None,
                        source=SIM_VERSION + "-offline-truth",
                    )
                )
        f["source"] = SIM_VERSION
        frames.append(f)
    return (
        pd.concat(frames, ignore_index=True),
        pd.DataFrame(truth),
        pd.DataFrame(events, columns=["vehicle_id", "component", "date", "source"]),
    )
