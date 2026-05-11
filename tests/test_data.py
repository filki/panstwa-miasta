from panstwa_miasta.data import COUNTRIES, JOBS, NAMES


def test_data_sets_not_empty():
    assert len(NAMES) > 100
    assert len(JOBS) > 1400
    assert len(COUNTRIES) > 100


def test_sample_data_presence():
    assert "polska" in COUNTRIES
    assert "niemcy" in COUNTRIES
    assert "adam" in NAMES
    assert isinstance(JOBS, set)
    assert "adwokat" in JOBS
    assert "agent" in JOBS
