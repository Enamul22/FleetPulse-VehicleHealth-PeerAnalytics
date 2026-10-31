"""Offline healthy calibration; inference reads transparent frozen coefficients only."""

import numpy as np
import pandas as pd
from .config import SIGNALS, MODELS, VERSION

FEATURES = [
    "constant",
    "model_BIR",
    "model_CED",
    "model_ELM",
    "ambient_20",
    "load",
    "rpm_1000",
    "rpm_load",
    "ambient_load",
]
BOUNDS = {"ambient_c": [-30.0, 45.0], "load": [0.1, 0.95], "rpm": [700.0, 4200.0]}


def design(f):
    a = f.ambient_c.to_numpy(float) / 20
    load_value = f.load.to_numpy(float)
    r = f.rpm.to_numpy(float) / 1000
    return np.column_stack(
        [
            np.ones(len(f)),
            *[(f.model_id == m).astype(float) for m in ["BIR", "CED", "ELM"]],
            a,
            load_value,
            r,
            r * load_value,
            a * load_value,
        ]
    )


def healthy_expectation(f):
    """Simulator's healthy signal equations, used to generate observations, never by inference."""
    m = f.model_id.map({"ALD": 0.0, "BIR": 1.0, "CED": 2.0, "ELM": 3.0}).to_numpy()
    a = f.ambient_c.to_numpy()
    load_value = f.load.to_numpy()
    r = f.rpm.to_numpy() / 1000
    return dict(
        oil=72 + 0.3 * a + 10 * load_value + 3 * r + 0.5 * m + 0.8 * (a / 20) * load_value,
        cooling=78 + 0.18 * a + 5 * load_value + 2 * r + 0.3 * m,
        lubrication=1.2 + 0.55 * r + 0.5 * load_value + 0.07 * m - 0.002 * a,
        charging=14.3 - 0.007 * a - 0.12 * load_value + 0.02 * m,
        smoothness=0.7 + 0.25 * r + 0.6 * load_value + 0.2 * r * load_value + 0.04 * m,
    )


def healthy_population(seed, n=12000, prefix="CAL"):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(
        dict(
            vehicle_id=[f"{prefix}-{i // 60:05}" for i in range(n)],
            model_id=np.repeat(np.array(list(MODELS))[rng.integers(0, 4, int(np.ceil(n / 60)))], 60)[:n],
            ambient_c=rng.uniform(-30, 45, n),
            load=rng.uniform(0.1, 0.95, n),
            rpm=rng.uniform(700, 4200, n),
        )
    )
    expected = healthy_expectation(f)
    # Persistent sensor characteristics are independent of component condition and country.
    vehicle_noise = rng.normal(0, 0.15, (int(np.ceil(n / 60)), 5))
    for j, (k, s) in enumerate(SIGNALS.items()):
        f[s["signal"]] = expected[k] + s["noise"] * (
            rng.normal(0, 1, n) + np.repeat(vehicle_noise[:, j], 60)[:n]
        )
    return f


def tolerance(residual, floor):
    x = np.asarray(residual, float)
    x = x[np.isfinite(x)]
    if not len(x):
        raise ValueError("Calibration residuals must be finite and nonempty")
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    return max(float(floor), med + 3 * 1.4826 * mad)


def predict(f, baseline, component):
    # Explicit whitelist: neither labels, country, age, another target signal nor future rows are inputs.
    return design(f) @ np.asarray(baseline["signals"][component]["coefficients"])


def calibrate():
    from sklearn.linear_model import Ridge

    train = healthy_population(4101, 18000, "HEALTHY-TRAIN")
    dev = healthy_population(4102, 9000, "HEALTHY-DEV")
    x = design(train)
    xd = design(dev)
    baseline = dict(
        version=VERSION,
        method="Ridge(alpha=0.000001, fit_intercept=False, solver=svd)",
        features=FEATURES,
        bounds=BOUNDS,
        training_seed=4101,
        development_seed=4102,
        training_rows=len(train),
        development_rows=len(dev),
        signals={},
    )
    for k, s in SIGNALS.items():
        model = Ridge(alpha=1e-6, fit_intercept=False, solver="svd").fit(x, train[s["signal"]])
        residual = (dev[s["signal"]].to_numpy() - xd @ model.coef_) * s["direction"]
        tol = tolerance(residual, s["floor"])
        if tol >= s["severe"]:
            raise ValueError("Severe reference must exceed healthy tolerance")
        groups = dev[["model_id", "ambient_c", "load"]].copy()
        groups["error"] = residual
        groups["ambient_bin"] = pd.cut(groups.ambient_c, [-31, -10, 10, 30, 46]).astype(str)
        groups["load_bin"] = pd.cut(groups.load, [0.09, 0.4, 0.7, 0.96]).astype(str)
        biases = groups.groupby(["model_id", "ambient_bin", "load_bin"], observed=True).error.mean()
        baseline["signals"][k] = dict(
            coefficients=model.coef_.tolist(),
            healthy_tolerance=tol,
            severe_reference=s["severe"],
            unit=s["unit"],
            direction=s["direction"],
            development_mae=float(np.abs(residual).mean()),
            development_max_context_bias=float(biases.abs().max()),
            tolerance_method="median(signed adverse residual) + 3 * 1.4826 * MAD, with unit-specific floor",
        )
    return baseline
