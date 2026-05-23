"""Testy modułu share_store (LRU + integracja z zapisem wyniku)."""

import pytest

from panstwa_miasta import share_store


@pytest.fixture(autouse=True)
def _clear_store():
    share_store.clear_share_snapshots()
    yield
    share_store.clear_share_snapshots()


def test_record_and_get_roundtrip():
    share_store.record_finished_game("r1", {"A": 10, "B": 5}, "A")
    snap = share_store.get_snapshot("r1")
    assert snap is not None
    assert snap.room_id == "r1"
    assert snap.host_name == "A"
    assert snap.scores == {"A": 10, "B": 5}


def test_eviction_when_over_capacity(monkeypatch):
    monkeypatch.setattr(share_store, "_MAX_ENTRIES", 3)
    share_store.record_finished_game("a", {"p": 1}, "")
    share_store.record_finished_game("b", {"p": 2}, "")
    share_store.record_finished_game("c", {"p": 3}, "")
    share_store.record_finished_game("d", {"p": 4}, "")
    assert share_store.get_snapshot("a") is None
    assert share_store.get_snapshot("d") is not None


def test_record_overwrites_same_room():
    share_store.record_finished_game("r9", {"A": 1}, "h")
    share_store.record_finished_game("r9", {"A": 99}, "h2")
    assert share_store.get_snapshot("r9").scores["A"] == 99
    assert share_store.get_snapshot("r9").host_name == "h2"
