"""HTTP API ręcznej kolejki słownika (bez AI)."""

from __future__ import annotations

from fastapi import APIRouter

from ..api_models import WordReportIn, WordReportOut
from ..word_queue import submit_dictionary_intake

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])


@router.post("/suggestions", response_model=WordReportOut)
async def post_dictionary_suggestion(body: WordReportIn) -> WordReportOut:
    result = await submit_dictionary_intake(
        word=body.word,
        category=body.category,
        letter=body.starting_letter,
    )
    return WordReportOut.model_validate(result)
