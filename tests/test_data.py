from panstwa_miasta.data import COUNTRIES, JOBS, MIASTA, NAMES


def test_data_sets_not_empty():
    assert len(NAMES) > 100
    assert len(MIASTA) > 10_000  # PL (Wikidata) + pl.wiki „A” + GeoNames (≥15k, bez PL)
    assert len(JOBS) > 1400
    assert len(COUNTRIES) > 100


def test_sample_data_presence():
    assert "polska" in COUNTRIES
    assert "niemcy" in COUNTRIES
    assert "adam" in NAMES
    assert isinstance(JOBS, set)
    assert "adwokat" in JOBS
    assert "agent" in JOBS
    assert "warszawa" in MIASTA
