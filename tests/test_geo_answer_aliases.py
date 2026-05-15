"""Testy aliasów geo i foldowania niemieckiego zapisu."""

from __future__ import annotations

from panstwa_miasta.geo_answer_aliases import (
    fold_german_geo_spelling,
    resolve_city_answer,
    resolve_country_answer,
)


def test_fold_german_geo_spelling() -> None:
    assert fold_german_geo_spelling("düsseldorf") == "dusseldorf"
    assert fold_german_geo_spelling("straße") == "strasse"
    assert fold_german_geo_spelling("münchen") == "munchen"


def test_resolve_city_stockholm_to_polish() -> None:
    assert resolve_city_answer("stockholm") == "sztokholm"


def test_resolve_city_german_fold_only() -> None:
    assert resolve_city_answer("düsseldorf") == "dusseldorf"


def test_resolve_country_rpa_long_form() -> None:
    assert resolve_country_answer("republika południowej afryki") == "południowa afryka"
    assert resolve_country_answer("rpa") == "południowa afryka"
