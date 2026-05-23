import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from panstwa_miasta.appeal_tokens import issue_appeal_token
from panstwa_miasta.appeals_explain import explain_zero_score
from panstwa_miasta.appeals_service import submit_appeal
from panstwa_miasta.db import (
    fetch_dictionary_suggestion,
    init_db,
    insert_dictionary_suggestion,
    save_game_transcript,
    set_dictionary_suggestion_status,
)
from panstwa_miasta.main import app
from panstwa_miasta.manager import ConnectionManager

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


def test_explain_zero_score_wrong_letter():
    code, message = explain_zero_score("Państwo", "Berlin", "W", veto_rejected=False)
    assert code == "wrong_letter"
    assert "liter" in message.lower()


def test_explain_zero_score_empty():
    code, message = explain_zero_score("Miasto", "", "W", veto_rejected=False)
    assert code == "empty"
    assert "puste" in message.lower()


def test_explain_zero_score_empty_whitespace():
    """Same whitespace-only input treated as empty."""
    code, message = explain_zero_score("Państwo", "   ", "W", veto_rejected=False)
    assert code == "empty"


def test_explain_zero_score_too_short_animal():
    """Zwierzę < 2 chars after normalization → too_short."""
    code, message = explain_zero_score("Zwierzę", "K", "K", veto_rejected=False)
    assert code == "too_short"


def test_explain_zero_score_too_short_plant():
    """Roślina < 2 chars after normalization → too_short."""
    code, message = explain_zero_score("Roślina", "A", "A", veto_rejected=False)
    assert code == "too_short"


def test_explain_zero_score_veto_rejected():
    """Rzecz odrzucona przez veto."""
    code, message = explain_zero_score("Rzecz", "Aparat", "A", veto_rejected=True)
    assert code == "veto_rejected"


def test_explain_zero_score_not_in_dictionary():
    """Państwo spoza słownika → not_in_dictionary."""
    code, message = explain_zero_score("Państwo", "Nibylandia", "N", veto_rejected=False)
    assert code == "not_in_dictionary"


def test_explain_zero_score_unknown_category():
    """Nieznana kategoria → ValueError."""
    import pytest as pt

    with pt.raises(ValueError, match="unknown category"):
        explain_zero_score("NieIstnieje", "x", "X", veto_rejected=False)


def test_explain_zero_score_rzecz_default_fallback():
    """Rzecz bez veto — zwraca 'veto_rejected' (zgodnie z logiką kategorii VETO)."""
    code, message = explain_zero_score("Rzecz", "Xenon", "X", veto_rejected=False)
    # Rzecz bez veto przechodzi wszystkie checks i trafia na ostatni if category==VETO
    assert code == "veto_rejected"


def test_dictionary_validators_country():
    """_dictionary_validators returns correct validator for Państwo."""
    from panstwa_miasta.appeals_explain import _dictionary_validators

    validators = _dictionary_validators()
    assert "Państwo" in validators
    assert callable(validators["Państwo"])
    # Known country
    assert validators["Państwo"]("polska") is True


def test_answer_in_dictionary_veto_category():
    """VETO_CATEGORY (Rzecz) always returns True."""
    from panstwa_miasta.appeals_explain import _answer_in_dictionary

    assert _answer_in_dictionary("Rzecz", "cokolwiek") is True


def test_answer_in_dictionary_unknown_category():
    """Category not in validators → True (optimistic)."""
    from panstwa_miasta.appeals_explain import _answer_in_dictionary

    assert _answer_in_dictionary("NieIstnieje", "x") is True


@pytest.mark.asyncio
async def test_submit_appeal_rejects_positive_cell():
    room_id = "appeal_room_pos"
    await save_game_transcript(
        room_id,
        {
            "rounds": [
                {
                    "round": 1,
                    "letter": "w",
                    "answers": {"Anna": {"Państwo": "Włochy"}},
                    "round_scores": {
                        "Anna": {"total": 15, "details": {"Państwo": 15}},
                    },
                    "veto_rejected": [],
                }
            ]
        },
    )
    mgr = ConnectionManager()
    with pytest.raises(HTTPException) as excinfo:
        await submit_appeal(mgr, room_id, "Anna", 1, "Państwo")
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_submit_appeal_returns_rule_message():
    room_id = "appeal_room_zero"
    await save_game_transcript(
        room_id,
        {
            "rounds": [
                {
                    "round": 1,
                    "letter": "w",
                    "answers": {"Anna": {"Państwo": "Wakanda"}},
                    "round_scores": {
                        "Anna": {"total": 0, "details": {"Państwo": 0}},
                    },
                    "veto_rejected": [],
                }
            ]
        },
    )
    mgr = ConnectionManager()
    result = await submit_appeal(mgr, room_id, "Anna", 1, "Państwo")
    assert result["reason_code"] == "not_in_dictionary"
    assert result["suggested_seed"] is False


def test_post_appeal_http_requires_token():
    room_id = "appeal_http"
    missing = client.post(
        f"/api/rooms/{room_id}/appeals",
        json={"player_name": "Anna", "round": 1, "category": "Państwo"},
    )
    assert missing.status_code == 401


@pytest.mark.asyncio
async def test_post_appeal_http_with_token():
    room_id = "appeal_http_ok"
    await save_game_transcript(
        room_id,
        {
            "rounds": [
                {
                    "round": 1,
                    "letter": "w",
                    "answers": {"Anna": {"Państwo": "Włochy"}},
                    "round_scores": {
                        "Anna": {"total": 0, "details": {"Państwo": 0}},
                    },
                    "veto_rejected": [],
                }
            ]
        },
    )
    token = issue_appeal_token(room_id, "Anna")
    response = client.post(
        f"/api/rooms/{room_id}/appeals",
        json={"player_name": "Anna", "round": 1, "category": "Państwo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "słowniku" in response.json()["message_pl"].lower()


@pytest.mark.asyncio
async def test_dictionary_suggestion_status_flow():
    suggestion_id = await insert_dictionary_suggestion(
        category="Państwo",
        proposed_norm="testlandia",
        proposed_display="Testlandia",
        target_seed="countries",
        room_id="r1",
        player_name="Anna",
        letter="t",
        round_no=1,
        ai_explanation="test",
    )
    row = await fetch_dictionary_suggestion(suggestion_id)
    assert row is not None
    assert row["status"] == "pending"
    assert await set_dictionary_suggestion_status(suggestion_id, "accepted", review_note="ok")
    row2 = await fetch_dictionary_suggestion(suggestion_id)
    assert row2 is not None
    assert row2["status"] == "accepted"
