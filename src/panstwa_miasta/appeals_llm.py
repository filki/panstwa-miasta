"""Optional LLM layer for post-game dictionary suggestions."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .db import insert_dictionary_suggestion
from .manager import normalize_text

_CATEGORY_TO_SEED: dict[str, str] = {
    "Państwo": "countries",
    "Miasto": "cities",
    "Imię": "names",
    "Zawód": "jobs",
    "Zwierzę": "animals",
    "Roślina": "plants",
}


def appeals_llm_enabled() -> bool:
    return (os.environ.get("PM_APPEALS_LLM") or "").lower() in ("1", "true", "yes")


def _llm_config() -> tuple[str, str, str] | None:
    if not appeals_llm_enabled():
        return None
    api_key = (
        os.environ.get("PM_APPEALS_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    ).strip()
    if not api_key:
        return None
    endpoint = (
        os.environ.get("PM_APPEALS_LLM_ENDPOINT") or "https://api.openai.com/v1/chat/completions"
    ).strip()
    model = (os.environ.get("PM_APPEALS_LLM_MODEL") or "gpt-4o-mini").strip()
    return endpoint, api_key, model


async def _call_llm(prompt: str) -> dict[str, Any] | None:
    cfg = _llm_config()
    if cfg is None:
        return None
    endpoint, api_key, model = cfg
    timeout = float(os.environ.get("PM_APPEALS_LLM_TIMEOUT_SEC", "12") or "12")
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Odpowiadasz wyłącznie JSON: "
                    '{"verdict":"reject"|"suggest_seed","explanation":"...","proposed_entry":"...","target_table":"countries|cities|names|jobs|animals|plants"}'
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError):
        return None

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


async def maybe_enqueue_dictionary_suggestion(
    *,
    room_id: str,
    player_name: str,
    round_no: int,
    category: str,
    letter: str,
    answer_raw: str,
    reason_code: str,
) -> int | None:
    if reason_code not in ("not_in_dictionary", "veto_rejected"):
        return None
    if category not in _CATEGORY_TO_SEED:
        return None

    prompt = (
        f"Gra Państwa-Miasta po polsku. Litera rundy: {letter}. "
        f"Kategoria: {category}. Odpowiedź gracza: {answer_raw!r}. "
        f"Powód 0 pkt: {reason_code}. "
        "Jeśli wpis wygląda na poprawny dla kategorii, zwróć suggest_seed z proposed_entry; "
        "w przeciwnym razie reject."
    )
    llm = await _call_llm(prompt)
    if llm is None or llm.get("verdict") != "suggest_seed":
        return None

    proposed = str(llm.get("proposed_entry") or answer_raw).strip()
    if not proposed:
        return None
    target = str(llm.get("target_table") or _CATEGORY_TO_SEED[category]).strip()
    if target not in set(_CATEGORY_TO_SEED.values()):
        target = _CATEGORY_TO_SEED[category]
    explanation = str(llm.get("explanation") or "").strip()

    return await insert_dictionary_suggestion(
        category=category,
        proposed_norm=normalize_text(proposed),
        proposed_display=proposed,
        target_seed=target,
        room_id=room_id,
        player_name=player_name,
        letter=letter,
        round_no=round_no,
        ai_explanation=explanation,
    )
