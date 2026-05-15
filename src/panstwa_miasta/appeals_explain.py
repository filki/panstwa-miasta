"""Deterministic explanations for zero-point answers (post-game appeals)."""

from __future__ import annotations

from collections.abc import Callable

from panstwa_miasta.data import COUNTRIES, MIASTA, NAMES, ROSLINY, ZWIERZETA, job_answer_accepted
from panstwa_miasta.manager import (
    GAME_CATEGORIES,
    VETO_CATEGORY,
    _answer_first_letter_matches_round,
    _fauna_flora_norm_valid,
    normalize_text,
)

REASON_MESSAGES: dict[str, str] = {
    "empty": "Puste pole — za to dostajesz 0 punktów.",
    "wrong_letter": "Odpowiedź musi zaczynać się od litery wylosowanej w tej rundzie.",
    "too_short": "Zwierzę i roślina muszą mieć co najmniej 2 znaki po normalizacji.",
    "not_in_dictionary": "Tego wpisu nie ma w słowniku gry dla tej kategorii.",
    "veto_rejected": "Gracze odrzucili odpowiedź w kategorii Rzecz głosowaniem „nie”.",
}


def _dictionary_validators() -> dict[str, Callable[[str], bool]]:
    from .geo_answer_aliases import resolve_city_answer, resolve_country_answer

    return {
        "Państwo": lambda n: resolve_country_answer(n) in COUNTRIES,
        "Miasto": lambda n: resolve_city_answer(n) in MIASTA,
        "Imię": lambda n: n in NAMES,
        "Zawód": job_answer_accepted,
        "Zwierzę": lambda n: _fauna_flora_norm_valid(n, ZWIERZETA),
        "Roślina": lambda n: _fauna_flora_norm_valid(n, ROSLINY),
    }


def _answer_in_dictionary(category: str, ans_norm: str) -> bool:
    if category == VETO_CATEGORY:
        return True
    validate = _dictionary_validators().get(category)
    return validate(ans_norm) if validate is not None else True


def explain_zero_score(
    category: str,
    ans_raw: str,
    letter: str,
    *,
    veto_rejected: bool,
) -> tuple[str, str]:
    if category not in GAME_CATEGORIES:
        raise ValueError(f"unknown category: {category}")

    trimmed = (ans_raw or "").strip()
    if not trimmed:
        return "empty", REASON_MESSAGES["empty"]
    if not _answer_first_letter_matches_round(trimmed, letter):
        return "wrong_letter", REASON_MESSAGES["wrong_letter"]

    ans_norm = normalize_text(trimmed)
    if category in ("Zwierzę", "Roślina") and len(ans_norm) < 2:
        return "too_short", REASON_MESSAGES["too_short"]

    if category == VETO_CATEGORY and veto_rejected:
        return "veto_rejected", REASON_MESSAGES["veto_rejected"]

    if not _answer_in_dictionary(category, ans_norm):
        return "not_in_dictionary", REASON_MESSAGES["not_in_dictionary"]

    if category == VETO_CATEGORY:
        return "veto_rejected", REASON_MESSAGES["veto_rejected"]

    return "not_in_dictionary", REASON_MESSAGES["not_in_dictionary"]
