"""Modele Pydantic dla HTTP API (odpowiedzi i parametry ścieżki)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# ID pokoju: alfanumeryczne + _ - (bez znaków specjalnych ścieżki).
RoomIdPath = Annotated[
    str,
    StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,64}$", strip_whitespace=True),
]

# Nick gracza: bez separatorów ścieżki URL (? i \); # dozwolone po dekodowaniu %23.
NICKNAME_MAX_LENGTH = 16
ClientNamePath = Annotated[
    str,
    StringConstraints(
        pattern=rf"^[^?\\]{{1,{NICKNAME_MAX_LENGTH}}}$",
        strip_whitespace=True,
    ),
]


class ActiveRoomRow(BaseModel):
    """Wiersz listy publicznych lobby na stronie głównej."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., max_length=64)
    players: int = Field(..., ge=0)
    host: str = Field(..., max_length=200)
    current_round: int = Field(..., ge=0)
    max_rounds: int = Field(..., ge=1)
    time_limit: int = Field(..., ge=1)
    visibility: Literal["public", "private"]
    visibility_label: str = Field(..., max_length=32)


class ShareSnapshotOut(BaseModel):
    """Zapis wyniku końcowego gry (udostępnianie / OG)."""

    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(..., max_length=64)
    host_name: str = Field(default="", max_length=200)
    scores: dict[str, int] = Field(default_factory=dict)


class QuickJoinOut(BaseModel):
    """Wynik szybkiego dołączenia do publicznego lobby."""

    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(..., max_length=64)
    created: bool
    max_rounds: int = Field(5, ge=1, le=50)
    time_limit: int = Field(90, ge=10, le=600)


class CreateRoomIn(BaseModel):
    """Parametry nowego pokoju (identyfikator wydaje serwer)."""

    model_config = ConfigDict(extra="forbid")

    rounds: int = Field(5, ge=1, le=50)
    limit: int = Field(90, ge=10, le=600)
    visibility: Literal["public", "private"] = "public"


class CreateRoomOut(BaseModel):
    """Nowy kod pokoju do pierwszego połączenia WebSocket."""

    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(..., max_length=64)
    max_rounds: int = Field(..., ge=1, le=50)
    time_limit: int = Field(..., ge=10, le=600)
    visibility: Literal["public", "private"]


class AppealIn(BaseModel):
    """Odwołanie gracza do własnej odpowiedzi z 0 pkt po zakończeniu gry."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    player_name: str = Field(..., min_length=1, max_length=80)
    round: int = Field(..., ge=1, le=50)
    category: str = Field(..., min_length=1, max_length=32)


class AppealOut(BaseModel):
    """Wyjaśnienie regułowe (i ewentualnie propozycja wpisu do słownika)."""

    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(..., max_length=64)
    message_pl: str = Field(..., max_length=2000)
    suggested_seed: bool = False
    suggestion_id: int | None = None


class WordReportIn(BaseModel):
    """Zgłoszenie słowa spoza słownika do kolejki AI."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    word: str = Field(..., min_length=1, max_length=120)
    category: str = Field(..., min_length=1, max_length=32)
    starting_letter: str = Field(..., min_length=1, max_length=8)


class WordReportOut(BaseModel):
    """Wynik zgłoszenia słowa do kolejki AI."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["created", "exists"]
    suggestion_id: int = Field(..., ge=1)
    message_pl: str = Field(..., max_length=500)


class WordCheckReasonIn(BaseModel):
    """Zapytanie o status zgłoszenia słowa w kolejce AI."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    word: str = Field(..., min_length=1, max_length=120)
    category: str = Field(..., min_length=1, max_length=32)
    starting_letter: str = Field(..., min_length=1, max_length=8)


class WordCheckReasonOut(BaseModel):
    """Status zgłoszenia słowa w kolejce AI."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["missing", "pending", "accepted", "rejected", "error"]
    message_pl: str = Field(..., max_length=500)
    ai_reason: str | None = Field(default=None, max_length=2000)
    created_at: str | None = Field(default=None, max_length=40)


class WordWorkerPendingItem(BaseModel):
    """Wiersz kolejki pending dla workera."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)
    category: str = Field(..., max_length=32)
    proposed_display: str = Field(..., max_length=120)
    proposed_norm: str = Field(..., max_length=120)
    target_seed: str = Field(..., max_length=32)
    letter: str = Field(..., max_length=8)
    room_id: str = Field(..., max_length=64)
    player_name: str = Field(..., max_length=64)
    round: int = Field(..., ge=0)
    created_at: int = Field(..., ge=0)


class WordWorkerPendingOut(BaseModel):
    """Partia pending dla workera."""

    model_config = ConfigDict(extra="forbid")

    items: list[WordWorkerPendingItem]
    next_after_id: int = Field(..., ge=0)


class WordWorkerDecisionIn(BaseModel):
    """Decyzja workera AI nad zgłoszeniem."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "rejected", "error"]
    ai_explanation: str | None = Field(default=None, max_length=2000)
    review_note: str | None = Field(default=None, max_length=2000)


class WordWorkerDecisionOut(BaseModel):
    """Potwierdzenie zapisu decyzji workera."""

    model_config = ConfigDict(extra="forbid")

    suggestion_id: int = Field(..., ge=1)
    status: Literal["accepted", "rejected", "error"]
