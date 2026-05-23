import pytest

from panstwa_miasta import data
from panstwa_miasta.db import load_thing_norms
from panstwa_miasta.manager import Room
from panstwa_miasta.things_lexicon import persist_accepted_things


@pytest.mark.asyncio
async def test_persist_accepted_things_inserts_after_positive_score():
    room = Room("room_things")
    room.answers_received = {
        "Ada": {"Rzecz": "Tornister"},
        "Bob": {"Rzecz": "Taboret"},
    }
    round_scores = {
        "Ada": {"total": 10, "details": {"Rzecz": 10}},
        "Bob": {"total": 0, "details": {"Rzecz": 0}},
    }

    await persist_accepted_things(room, round_scores, set())

    norms = await load_thing_norms()
    assert "tornister" in norms
    assert "taboret" not in norms
    assert "tornister" in data.THINGS


@pytest.mark.asyncio
async def test_persist_accepted_things_skips_veto_rejected():
    room = Room("room_things_veto")
    room.answers_received = {"Ada": {"Rzecz": "Tamburyn"}}
    round_scores = {"Ada": {"total": 10, "details": {"Rzecz": 10}}}

    await persist_accepted_things(room, round_scores, {"Ada"})

    norms = await load_thing_norms()
    assert "tamburyn" not in norms
