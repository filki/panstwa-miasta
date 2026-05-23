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


def test_pl_game_requires_at_least_one_polish_letter():
    assert not keep_city_name_for_pl_game("123")
    assert not keep_city_name_for_pl_game("---")


def test_geonames_seed_requires_polish_letter_and_rejects_bad_chars():
    assert not keep_city_name_for_geonames_seed("   ")
    assert not keep_city_name_for_geonames_seed("999")
    assert not keep_city_name_for_geonames_seed("Stantsiya Novyy Afon™")
