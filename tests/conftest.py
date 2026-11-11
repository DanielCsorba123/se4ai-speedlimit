from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def raw_dir() -> Path:
    """Directory with the small CSV fixtures (see fixtures/make_fixtures.py)."""
    return FIXTURES


@pytest.fixture
def tiny_readings() -> Path:
    """Readings of Jan 5-6 (2 x 24 h x 17 series), original format incl. header."""
    return FIXTURES / "readings_tiny.csv"


@pytest.fixture
def tiny_readings_n1() -> Path:
    """Same rows as tiny_readings but without the header line, like the N+1 file."""
    return FIXTURES / "readings_n1_tiny.csv"


@pytest.fixture
def tiny_accidents() -> Path:
    """First 20 accident rows of Jan 5-6, LicencePlate included."""
    return FIXTURES / "accidents_tiny.csv"


@pytest.fixture
def faulty_readings() -> Path:
    """tiny_readings with every slide-17 fault class injected (D19)."""
    return FIXTURES / "readings_faults.csv"


@pytest.fixture
def config_path() -> Path:
    return ROOT / "config.yaml"
