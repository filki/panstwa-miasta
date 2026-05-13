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
ClientNamePath = Annotated[
    str,
    StringConstraints(pattern=r"^[^?\\]{1,80}$", strip_whitespace=True),
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
