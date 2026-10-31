# Reproducibility and manual release

Python 3.12; tested 3.12.14. `requirements.txt` includes `requirements.lock.txt`, which pins all installed packages. scikit-learn fitting is offline; operational prediction is a transparent JSON coefficient dot product. No pickle/model server is shipped.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m pip check
python -m pytest -q
ruff check .
ruff format --check .
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m fleetpulse.validate
streamlit run app.py
```

Included prepared data is sufficient. Tests and launch do not need a FleetCare/ServicePlan checkout, private file, login, database URL, online inference or an API key. The Streamlit default Deploy control is not an application deployment; this delivery does not activate it.

## Offline full regeneration

Use a read-only FleetCare Git checkout containing `0f3663e31ea6610eb2a00256ca0d984ebc7c586b`:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m fleetpulse.prepare \
  --fleetcare /path/to/FleetCare-PredictiveMaintenance \
  --output data/prepared --evaluation data/evaluation
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m fleetpulse.validate
```

Preparation reads canonical Git blobs, freezes development calibration, generates extension observations/hidden offline labels, computes all monthly features/scores/peers, and writes a complete checksummed bundle. Never prepare into either reference project. Regenerate while the app is stopped; restart after replacing the entire bundle. On startup a manifest fingerprint keys the cache; checksum mismatch fails visibly rather than serving a mixed revision.

Seed 20261029 uses stable SHA256-derived per-vehicle streams, sorted iteration and explicit timestamp semantics. Calibration seeds 4101/4102 are distinct from held-out evaluation. Tests regenerate sample vehicle observations and calibration in fresh Python processes under different hash seeds with exact hash equality. Full canonical counts/counter identities and replay scoring from shipped observations are checked. Use the locked stack and one BLAS thread for byte-level same-platform reproducibility; cross-platform floating-point variation is assessed by tight numerical tolerances, not asserted bitwise identical.

## Revision policy

First release: `fp-daily-1`, `fp-index-1`, `fp-peer-1`. A future baseline/feature/weight/scale change requires a new score revision and explicit recomputation/review of the full historical bundle. A peer-rule change requires a new reference revision. Do not change December and silently refit earlier months, mix old/new component means, or present scores from different policies as directly comparable without disclosure.

## Manual Streamlit Community Cloud

After review: choose `Enamul22/FleetPulse-VehicleHealth-PeerAnalytics`, branch `main`, entry point `app.py`, Python `3.12`. **Secrets remain empty.** Requirements and prepared data are committed. No hosting app/deployment, paid resource or database is provisioned by this implementation. Leave the two completed applications’ repositories/secrets/deployments untouched.
