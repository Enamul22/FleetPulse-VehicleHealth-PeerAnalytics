import json
import pytest
from fleetpulse.config import DATA
from fleetpulse.validate import scenario


@pytest.fixture(scope="session")
def baseline():
    return json.loads((DATA / "baseline.json").read_text())


@pytest.fixture
def observations(baseline):
    return scenario(baseline, noise=False)
