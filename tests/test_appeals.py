import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

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


def test_post_appeal_http():
    room_id = "appeal_http"
    client.post(
        f"/api/rooms/{room_id}/appeals",
        json={"player_name": "Anna", "round": 1, "category": "Państwo"},
    )
    # Missing transcript -> 404
    missing = client.post(
        f"/api/rooms/{room_id}/appeals",
        json={"player_name": "Anna", "round": 1, "category": "Państwo"},
    )
    assert missing.status_code == 404


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
    assert await set_dictionary_suggestion_status(suggestion_id, "approved", review_note="ok")
    row2 = await fetch_dictionary_suggestion(suggestion_id)
    assert row2 is not None
    assert row2["status"] == "approved"
