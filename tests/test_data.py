import pytest
from panstwa_miasta.data import NAMES, JOBS, COUNTRIES

def test_data_sets_not_empty():
    assert len(NAMES) > 100
    assert len(JOBS) > 0
    assert len(COUNTRIES) > 100

def test_sample_data_presence():
    assert "polska" in COUNTRIES
    assert "niemcy" in COUNTRIES
    assert "adam" in NAMES
    # Check if some job is loaded (depends on txt files, but at least we can check type)
    assert isinstance(JOBS, set)
