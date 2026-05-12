from panstwa_miasta.data import COUNTRIES, JOBS, MIASTA, NAMES, ROSLINY, ZWIERZETA


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


def test_miasta_ascii_without_polish_diacritics():
    """Seed ma „kalińingrad” (ń); alias bez ogonków musi zaliczać walidację."""
    assert "kalińingrad" in MIASTA
    assert "kaliningrad" in MIASTA


def test_rosliny_ascii_without_polish_diacritics():
    """Flora: „jabłoń” w seedzie → „jablon” bez ł zalicza."""
    assert "jabłoń" in ROSLINY
    assert "jablon" in ROSLINY


def test_zwierzeta_extra_and_ascii_aliases():
    """``ZWIERZETA_EXTRA`` + alias ASCII (np. źrebak / żrebak / zrebak, koza)."""
    assert "źrebak" in ZWIERZETA
    assert "żrebak" in ZWIERZETA
    assert "zrebak" in ZWIERZETA
    assert "koza" in ZWIERZETA
