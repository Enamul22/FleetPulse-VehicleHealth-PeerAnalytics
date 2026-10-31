from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/prepared"
EVALUATION = ROOT / "data/evaluation"
FLEETCARE_REF = "0f3663e31ea6610eb2a00256ca0d984ebc7c586b"
SERVICEPLAN_REF = "5c3e9dc40a083495def3623f61c60985418a5653"
VERSION = "fp-index-1"
PEER_VERSION = "fp-peer-1"
SIM_VERSION = "fp-daily-1"
MODELS = {"ALD": "Alder Compact", "BIR": "Birch Sedan", "CED": "Cedar Van", "ELM": "Elm Utility"}
SIGNALS = {
    "oil": dict(
        label="Oil thermal behaviour",
        signal="oil_c",
        unit="°C",
        direction=1,
        severe=28.0,
        floor=0.25,
        noise=1.1,
        investigate="Review oil-temperature readings, operating load and the measurement setup.",
    ),
    "cooling": dict(
        label="Cooling behaviour",
        signal="coolant_c",
        unit="°C",
        direction=1,
        severe=20.0,
        floor=0.2,
        noise=0.8,
        investigate="Review coolant-temperature trends and cooling-system inspection findings.",
    ),
    "lubrication": dict(
        label="Lubrication behaviour",
        signal="pressure_bar",
        unit="bar",
        direction=-1,
        severe=1.8,
        floor=0.025,
        noise=0.08,
        investigate="Verify oil-pressure measurements and lubrication checks under comparable operating conditions.",
    ),
    "charging": dict(
        label="Charging behaviour",
        signal="voltage_v",
        unit="V",
        direction=-1,
        severe=1.7,
        floor=0.02,
        noise=0.06,
        investigate="Review charging-voltage readings and electrical connections while charging is expected.",
    ),
    "smoothness": dict(
        label="Mechanical smoothness",
        signal="vibration_mm_s",
        unit="mm/s RMS",
        direction=1,
        severe=3.0,
        floor=0.04,
        noise=0.11,
        investigate="Review vibration readings, mounts and operating RPM/load before drawing a conclusion.",
    ),
}

MEASUREMENT_BOUNDS = {
    "oil": (-20.0, 180.0),
    "cooling": (-20.0, 150.0),
    "lubrication": (0.0, 9.0),
    "charging": (8.0, 17.0),
    "smoothness": (0.0, 12.0),
}
