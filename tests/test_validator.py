from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from panstwa_miasta.validator import WikipediaValidator


@pytest.fixture
async def validator():
    v = WikipediaValidator()
    yield v
    await v.close()


@pytest.mark.asyncio
async def test_validator_cache(validator):
    validator.cache["Zwierzę:lew"] = True
    assert await validator.validate("lew", "Zwierzę") is True


@pytest.mark.asyncio
async def test_validator_empty_term(validator):
    assert await validator.validate("", "Miasto") is False


@pytest.mark.asyncio
async def test_validator_short_term_fails_for_wiki_categories(validator):
    assert await validator.validate("A", "Zwierzę") is False
    assert await validator.validate("O", "Roślina") is False


@pytest.mark.asyncio
async def test_validator_search_wikidata_match(validator):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"search": [{"label": "Warszawa", "id": "Q270"}]}

    with patch.object(validator.client, "get", AsyncMock(return_value=mock_resp)):
        entity_id = await validator._search_wikidata("warszawa")
        assert entity_id == "Q270"


@pytest.mark.asyncio
async def test_check_category_logic(validator):
    claims_city = {
        "P31": [
            {"mainsnak": {"datavalue": {"value": {"id": "Q515"}}}}  # city
        ]
    }
    assert validator._check_category(claims_city, "Zwierzę") is False
    claims_animal = {
        "P31": [
            {"mainsnak": {"datavalue": {"value": {"id": "Q729"}}}}  # animal
        ]
    }
    assert validator._check_category(claims_animal, "Zwierzę") is True
    assert validator._check_category(claims_city, "Unknown") is True
