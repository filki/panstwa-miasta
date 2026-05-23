import pytest
from pydantic import TypeAdapter, ValidationError

from panstwa_miasta.api_models import NICKNAME_MAX_LENGTH, ClientNamePath


def test_client_name_path_accepts_short_nickname():
    adapter = TypeAdapter(ClientNamePath)
    assert adapter.validate_python("FILIPINO") == "FILIPINO"


def test_client_name_path_rejects_overlong_nickname():
    adapter = TypeAdapter(ClientNamePath)
    with pytest.raises(ValidationError):
        adapter.validate_python("a" * (NICKNAME_MAX_LENGTH + 1))
