"""Generowanie niezgadywalnych identyfikatorów pokoi."""

from __future__ import annotations

import secrets
import string

_ROOM_ID_ALPHABET = string.ascii_letters + string.digits
_ROOM_ID_LENGTH = 10
_MAX_ALLOC_ATTEMPTS = 100


def generate_room_id_candidate() -> str:
    rng = secrets.SystemRandom()
    return "".join(rng.choice(_ROOM_ID_ALPHABET) for _ in range(_ROOM_ID_LENGTH))
