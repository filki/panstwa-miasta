"""Shared game constants."""

_FAUNA_FLORA: set[str] = {"Zwierzę", "Roślina"}

ALPHABET: str = "ABCDEFGHIJKLMNOPRSTUWZ"
LETTER_CYCLE_ROUNDS: int = len(ALPHABET)
GAME_CATEGORIES: list[str] = [
    "Państwo",
    "Miasto",
    "Rzecz",
    "Zwierzę",
    "Roślina",
    "Imię",
    "Zawód",
]
VETO_CATEGORY: str = "Rzecz"
RESULTS_PHASE_SECONDS: int = 30
STOP_SUBMIT_SECONDS: int = 10
STOP_SUBMIT_GRACE_SECONDS: float = 1.0
HOST_REASSIGN_GRACE_SECONDS: float = 5.0
QUICK_JOIN_DEFAULT_ROUNDS: int = 5
QUICK_JOIN_DEFAULT_TIME_LIMIT: int = 90
