from panstwa_miasta.city_name_rules import (
    keep_city_name_for_geonames_seed,
    keep_city_name_for_pl_game,
)


def test_keep_polish_city_names():
    assert keep_city_name_for_pl_game("Warszawa")
    assert keep_city_name_for_pl_game("Bielsko-Biała")
    assert keep_city_name_for_pl_game("Saint John’s")
    assert not keep_city_name_for_pl_game("Şabran")
    assert not keep_city_name_for_pl_game("Durrës")
    assert not keep_city_name_for_pl_game("")


def test_keep_geonames_seed_allows_common_foreign_latin():
    assert not keep_city_name_for_pl_game("Stantsiya Novyy Afon")
    assert keep_city_name_for_geonames_seed("Stantsiya Novyy Afon")
    assert keep_city_name_for_geonames_seed("Vancouver")
