"""Persist accepted answers in category ``Rzecz`` after a round is finalized."""

from __future__ import annotations

from .data import THINGS
from .db import upsert_thing
from .logger import get_logger
from .manager import VETO_CATEGORY, Room, normalize_text

logger = get_logger(__name__)


async def persist_accepted_things(
    room: Room,
    round_scores: dict[str, dict],
    veto_rejected: set[str],
) -> None:
    for player, score_data in round_scores.items():
        if player in veto_rejected:
            continue
        details = score_data.get("details", {})
        pts = details.get(VETO_CATEGORY, 0)
        if not isinstance(pts, int) or pts <= 0:
            continue
        raw = room.answers_received.get(player, {}).get(VETO_CATEGORY, "").strip()
        if not raw:
            continue
        norm = normalize_text(raw)
        if not norm:
            continue
        inserted = await upsert_thing(raw, norm)
        if inserted:
            THINGS.add(norm)
            logger.info("Accepted thing added to lexicon: %r", raw)
