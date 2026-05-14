"""HTTP API kolejki weryfikacji słów (RAG)."""

from __future__ import annotations

from fastapi import APIRouter

from ..api_models import WordCheckReasonIn, WordCheckReasonOut, WordReportIn, WordReportOut
from ..word_queue import lookup_word_reason, submit_word_report

router = APIRouter(prefix="/api/words", tags=["words"])


@router.post("/report", response_model=WordReportOut)
async def post_word_report(body: WordReportIn) -> WordReportOut:
    result = await submit_word_report(
        word=body.word,
        category=body.category,
        letter=body.starting_letter,
    )
    return WordReportOut.model_validate(result)


@router.post("/check-reason", response_model=WordCheckReasonOut)
async def post_word_check_reason(body: WordCheckReasonIn) -> WordCheckReasonOut:
    result = await lookup_word_reason(
        word=body.word,
        category=body.category,
        letter=body.starting_letter,
    )
    return WordCheckReasonOut.model_validate(result)
