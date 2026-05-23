"""Post-game appeal resolution (rules + optional dictionary suggestions)."""

from __future__ import annotations

from fastapi import HTTPException

from .appeals_explain import explain_zero_score
from .appeals_llm import maybe_enqueue_dictionary_suggestion
from .db import fetch_game_transcript
from .manager import GAME_CATEGORIES, ConnectionManager


def _transcript_rounds(manager: ConnectionManager, room_id: str) -> list[dict]:
    room = manager.rooms.get(room_id)
    if room is not None and room.game_over and room.round_history:
        return list(room.round_history)
    return []


async def _load_transcript_rounds(manager: ConnectionManager, room_id: str) -> list[dict]:
    in_memory = _transcript_rounds(manager, room_id)
    if in_memory:
        return in_memory
    stored = await fetch_game_transcript(room_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Brak transkryptu tej gry.")
    rounds = stored.get("rounds")
    if not isinstance(rounds, list):
        raise HTTPException(status_code=404, detail="Brak transkryptu tej gry.")
    return rounds


async def submit_appeal(
    manager: ConnectionManager,
    room_id: str,
    player_name: str,
    round_no: int,
    category: str,
) -> dict:
    if category not in GAME_CATEGORIES:
        raise HTTPException(status_code=422, detail="Nieznana kategoria.")

    rounds = await _load_transcript_rounds(manager, room_id)
    entry = next((item for item in rounds if int(item.get("round", -1)) == round_no), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono rundy w transkrypcie.")

    answers = entry.get("answers")
    if not isinstance(answers, dict) or player_name not in answers:
        raise HTTPException(status_code=403, detail="To nie jest Twoja odpowiedź.")

    round_scores = entry.get("round_scores")
    if not isinstance(round_scores, dict):
        raise HTTPException(status_code=404, detail="Brak wyników rundy.")
    player_score = round_scores.get(player_name)
    if not isinstance(player_score, dict):
        raise HTTPException(status_code=404, detail="Brak wyników gracza.")
    details = player_score.get("details")
    if not isinstance(details, dict):
        raise HTTPException(status_code=404, detail="Brak szczegółów punktacji.")
    points = details.get(category, 0)
    if not isinstance(points, int) or points > 0:
        raise HTTPException(status_code=400, detail="Odwołanie dotyczy tylko komórek z 0 punktów.")

    player_answers = answers.get(player_name)
    if not isinstance(player_answers, dict):
        raise HTTPException(status_code=404, detail="Brak odpowiedzi gracza.")
    ans_raw = str(player_answers.get(category, ""))
    letter = str(entry.get("letter", ""))
    veto_rejected = player_name in set(entry.get("veto_rejected") or [])

    reason_code, message_pl = explain_zero_score(
        category,
        ans_raw,
        letter,
        veto_rejected=veto_rejected,
    )

    result: dict = {
        "reason_code": reason_code,
        "message_pl": message_pl,
        "suggested_seed": False,
    }

    suggestion_id = await maybe_enqueue_dictionary_suggestion(
        room_id=room_id,
        player_name=player_name,
        round_no=round_no,
        category=category,
        letter=letter,
        answer_raw=ans_raw,
        reason_code=reason_code,
    )
    if suggestion_id is not None:
        result["suggested_seed"] = True
        result["suggestion_id"] = suggestion_id
        result["message_pl"] = (
            f"{message_pl} Zaproponowano dopisanie do słownika (oczekuje na weryfikację)."
        )

    return result
