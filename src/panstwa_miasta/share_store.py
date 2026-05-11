"""In-memory snapshots of finished games for share cards (OG meta + PNG)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

_MAX_ENTRIES = 200


@dataclass(frozen=True)
class ShareSnapshot:
    """Final scores after a completed game."""

    room_id: str
    scores: dict[str, int]
    host_name: str


# Oldest entries evicted when over capacity (room ids are small ints / strings).
_snapshots: OrderedDict[str, ShareSnapshot] = OrderedDict()


def record_finished_game(room_id: str, scores: dict[str, int], host_name: str) -> None:
    """Store final standings when a game ends (call once per finished game)."""
    snap = ShareSnapshot(
        room_id=room_id,
        scores=dict(scores),
        host_name=host_name or "",
    )
    _snapshots.pop(room_id, None)
    _snapshots[room_id] = snap
    _snapshots.move_to_end(room_id)
    while len(_snapshots) > _MAX_ENTRIES:
        _snapshots.popitem(last=False)


def get_snapshot(room_id: str) -> ShareSnapshot | None:
    """Return snapshot if we still have it."""
    snap = _snapshots.get(room_id)
    if snap is None:
        return None
    _snapshots.move_to_end(room_id)
    return snap
