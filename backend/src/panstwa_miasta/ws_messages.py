"""Walidacja przychodzących komunikatów WebSocket (Pydantic v2)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from .manager import GAME_CATEGORIES

_MAX_CHAT = 2000
_MAX_ANSWER_VALUE = 500
_MAX_KICK_TARGET = 120


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["chat"]
    text: str = Field(..., min_length=1, max_length=_MAX_CHAT)


class ReadyMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["ready"]


class NotReadyMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["not_ready"]


class RestartGameMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["restart_game"]
    rounds: int = Field(default=5, ge=1, le=50)
    limit: int = Field(default=90, ge=10, le=600)


class DissolveRoomMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["dissolve_room"]


class StopMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["stop"]


class AnswersMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["answers"]
    answers: dict[str, str] = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def _answers_shape(cls, v: dict[str, str]) -> dict[str, str]:
        allowed = frozenset(GAME_CATEGORIES)
        if len(v) > len(allowed):
            raise ValueError("too_many_categories")
        for key, val in v.items():
            if key not in allowed:
                raise ValueError(f"unknown_category:{key}")
            if len(val) > _MAX_ANSWER_VALUE:
                raise ValueError("answer_too_long")
        return v


class KickPlayerMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["kick_player"]
    target: str = Field(..., min_length=1, max_length=_MAX_KICK_TARGET)


class VetoVoteMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["veto_vote"]
    target: str = Field(..., min_length=1, max_length=_MAX_KICK_TARGET)
    vote: Literal["tak", "nie"]


WsInboundMessage = Annotated[
    ChatMessage
    | ReadyMessage
    | NotReadyMessage
    | RestartGameMessage
    | DissolveRoomMessage
    | StopMessage
    | AnswersMessage
    | KickPlayerMessage
    | VetoVoteMessage,
    Field(discriminator="type"),
]

ws_inbound_adapter: TypeAdapter[WsInboundMessage] = TypeAdapter(WsInboundMessage)
