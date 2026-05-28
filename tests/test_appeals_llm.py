"""Testy dla appeals_llm.py — LLM layer dla sugestii słownikowych."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPError

from panstwa_miasta.appeals_llm import (
    _call_llm,
    _llm_config,
    appeals_llm_enabled,
    maybe_enqueue_dictionary_suggestion,
)


class TestAppealsLlmEnabled:
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert appeals_llm_enabled() is False

    def test_enabled_with_1(self) -> None:
        with patch.dict(os.environ, {"PM_APPEALS_LLM": "1"}):
            assert appeals_llm_enabled() is True

    def test_enabled_with_true(self) -> None:
        with patch.dict(os.environ, {"PM_APPEALS_LLM": "true"}):
            assert appeals_llm_enabled() is True

    def test_disabled_with_0(self) -> None:
        with patch.dict(os.environ, {"PM_APPEALS_LLM": "0"}):
            assert appeals_llm_enabled() is False


class TestLlmConfig:
    def test_returns_none_when_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert _llm_config() is None

    def test_returns_none_when_no_api_key(self) -> None:
        with patch.dict(os.environ, {"PM_APPEALS_LLM": "1"}, clear=True):
            assert _llm_config() is None

    def test_returns_config_when_enabled_with_key(self) -> None:
        with patch.dict(
            os.environ,
            {"PM_APPEALS_LLM": "1", "PM_APPEALS_LLM_API_KEY": "sk-abc"},
            clear=True,
        ):
            cfg = _llm_config()
            assert cfg is not None
            endpoint, api_key, model = cfg
            assert api_key == "sk-abc"
            assert "openai.com" in endpoint
            assert model == "gpt-4o-mini"

    def test_custom_endpoint_and_model(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PM_APPEALS_LLM": "1",
                "PM_APPEALS_LLM_API_KEY": "tok_xyz",
                "PM_APPEALS_LLM_ENDPOINT": "https://custom-llm.example.com/v1",
                "PM_APPEALS_LLM_MODEL": "custom-model",
            },
            clear=True,
        ):
            cfg = _llm_config()
            assert cfg is not None
            endpoint, api_key, model = cfg
            assert endpoint == "https://custom-llm.example.com/v1"
            assert model == "custom-model"

    def test_falls_back_to_openai_api_key(self) -> None:
        with patch.dict(
            os.environ,
            {"PM_APPEALS_LLM": "1", "OPENAI_API_KEY": "sk-fallback"},
            clear=True,
        ):
            cfg = _llm_config()
            assert cfg is not None
            assert cfg[1] == "sk-fallback"


class TestCallLlm:
    @pytest.mark.asyncio
    async def test_returns_none_when_llm_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = await _call_llm("test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"verdict": "suggest_seed", "explanation": "Poprawne"}'}}
            ]
        }

        with (
            patch.dict(
                os.environ,
                {"PM_APPEALS_LLM": "1", "PM_APPEALS_LLM_API_KEY": "sk-test"},
                clear=True,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await _call_llm("test prompt")
            assert result is not None
            assert result["verdict"] == "suggest_seed"

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"PM_APPEALS_LLM": "1", "PM_APPEALS_LLM_API_KEY": "sk-test"},
                clear=True,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=HTTPError("Connection failed"))
            mock_client_cls.return_value = mock_client

            result = await _call_llm("test prompt")
            assert result is None


class TestMaybeEnqueueDictionarySuggestion:
    @pytest.mark.asyncio
    async def test_returns_none_for_unsupported_reason(self) -> None:
        result = await maybe_enqueue_dictionary_suggestion(
            room_id="r1",
            player_name="p1",
            round_no=1,
            category="Rzecz",
            letter="A",
            answer_raw="Aparat",
            reason_code="veto_rejected",
        )
        assert result is None  # "Rzecz" not in _CATEGORY_TO_SEED

    @pytest.mark.asyncio
    async def test_returns_none_if_llm_returns_none(self) -> None:
        with patch("panstwa_miasta.appeals_llm._call_llm", AsyncMock(return_value=None)):
            result = await maybe_enqueue_dictionary_suggestion(
                room_id="r1",
                player_name="p1",
                round_no=1,
                category="Państwo",
                letter="P",
                answer_raw="Polska",
                reason_code="not_in_dictionary",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_if_llm_verdict_is_reject(self) -> None:
        with patch(
            "panstwa_miasta.appeals_llm._call_llm",
            AsyncMock(return_value={"verdict": "reject", "explanation": "Niepoprawne"}),
        ):
            result = await maybe_enqueue_dictionary_suggestion(
                room_id="r1",
                player_name="p1",
                round_no=1,
                category="Miasto",
                letter="W",
                answer_raw="Warszawa",
                reason_code="not_in_dictionary",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_calls_insert_on_suggest_seed(self) -> None:
        with (
            patch(
                "panstwa_miasta.appeals_llm._call_llm",
                AsyncMock(
                    return_value={
                        "verdict": "suggest_seed",
                        "proposed_entry": "Warszawa",
                        "target_table": "cities",
                        "explanation": "Poprawne miasto",
                    }
                ),
            ),
            patch(
                "panstwa_miasta.appeals_llm.insert_dictionary_suggestion",
                AsyncMock(return_value=42),
            ),
        ):
            result = await maybe_enqueue_dictionary_suggestion(
                room_id="r1",
                player_name="p1",
                round_no=1,
                category="Miasto",
                letter="W",
                answer_raw="Warszawa",
                reason_code="not_in_dictionary",
            )
            assert result == 42

    @pytest.mark.asyncio
    async def test_uses_answer_raw_when_proposed_entry_empty(self) -> None:
        with (
            patch(
                "panstwa_miasta.appeals_llm._call_llm",
                AsyncMock(
                    return_value={
                        "verdict": "suggest_seed",
                        "proposed_entry": "",
                        "explanation": "",
                    }
                ),
            ),
            patch(
                "panstwa_miasta.appeals_llm.insert_dictionary_suggestion",
                AsyncMock(return_value=99),
            ) as mock_insert,
        ):
            result = await maybe_enqueue_dictionary_suggestion(
                room_id="r1",
                player_name="p1",
                round_no=1,
                category="Państwo",
                letter="P",
                answer_raw="Polska",
                reason_code="veto_rejected",
            )
            assert result == 99
            call_kwargs = mock_insert.call_args[1]
            assert "polska" in call_kwargs.get("proposed_norm", "")
