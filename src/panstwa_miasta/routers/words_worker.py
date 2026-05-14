"""Wewnętrzne HTTP API kolejki słów (n8n worker)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query

from ..api_models import WordWorkerDecisionIn, WordWorkerDecisionOut, WordWorkerPendingOut
from ..word_worker import apply_worker_decision, fetch_pending_batch, verify_words_worker_token

router = APIRouter(prefix="/api/internal/words", tags=["words-worker"])


@router.get("/pending", response_model=WordWorkerPendingOut)
async def get_pending_words(
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    after_id: Annotated[int, Query(ge=0)] = 0,
) -> WordWorkerPendingOut:
    verify_words_worker_token(authorization)
    result = await fetch_pending_batch(limit=limit, after_id=after_id)
    return WordWorkerPendingOut.model_validate(result)


@router.post("/{suggestion_id}/decision", response_model=WordWorkerDecisionOut)
async def post_word_decision(
    suggestion_id: int,
    body: WordWorkerDecisionIn,
    authorization: Annotated[str | None, Header()] = None,
) -> WordWorkerDecisionOut:
    verify_words_worker_token(authorization)
    result = await apply_worker_decision(
        suggestion_id,
        status=body.status,
        ai_explanation=body.ai_explanation,
        review_note=body.review_note,
    )
    return WordWorkerDecisionOut.model_validate(result)
