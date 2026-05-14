import pytest
from fastapi.testclient import TestClient

from panstwa_miasta.db import init_db
from panstwa_miasta.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


def test_word_report_disabled_by_default():
    response = client.post(
        "/api/words/report",
        json={"word": "Wakanda", "category": "Państwo", "starting_letter": "w"},
    )
    assert response.status_code == 503


def test_dictionary_intake_always_available():
    payload = {"word": "Wakanda", "category": "Państwo", "starting_letter": "w"}
    created = client.post("/api/dictionary/suggestions", json=payload)
    assert created.status_code == 200
    body = created.json()
    assert body["outcome"] == "created"
    assert body["suggestion_id"] >= 1
    assert "ręczn" in body["message_pl"].lower()

    duplicate = client.post("/api/dictionary/suggestions", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["outcome"] == "exists"


def test_word_report_and_check_reason(monkeypatch):
    monkeypatch.setenv("PM_RAG_QUEUE_ENABLED", "1")
    payload = {"word": "Wakanda", "category": "Państwo", "starting_letter": "w"}
    created = client.post("/api/words/report", json=payload)
    assert created.status_code == 200
    body = created.json()
    assert body["outcome"] == "created"
    assert body["suggestion_id"] >= 1

    duplicate = client.post("/api/words/report", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["outcome"] == "exists"

    pending = client.post("/api/words/check-reason", json=payload)
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending"
