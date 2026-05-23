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
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "created"
    assert "ai" in body["message_pl"].lower()


def test_dictionary_intake_always_available():
    payload = {"word": "Wakanda", "category": "Państwo", "starting_letter": "w"}
    created = client.post("/api/dictionary/suggestions", json=payload)
    assert created.status_code == 200
    body = created.json()
    assert body["outcome"] == "created"
    assert body["suggestion_id"] >= 1
    assert "dziękujemy" in body["message_pl"].lower()

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


def test_word_report_unknown_category():
    response = client.post(
        "/api/words/report",
        json={"word": "X", "category": "NieznanaKategoria", "starting_letter": "x"},
    )
    assert response.status_code == 422
    assert "kategor" in response.json()["detail"].lower()


def test_word_report_empty_word():
    response = client.post(
        "/api/words/report",
        json={"word": "   ", "category": "Państwo", "starting_letter": "p"},
    )
    assert response.status_code == 422


def test_word_report_bad_letter():
    response = client.post(
        "/api/words/report",
        json={"word": "Polska", "category": "Państwo", "starting_letter": "ab"},
    )
    assert response.status_code == 422
    assert "pojedynczym" in response.json()["detail"].lower()


def test_dictionary_intake_unknown_category():
    response = client.post(
        "/api/dictionary/suggestions",
        json={"word": "X", "category": "BadCat", "starting_letter": "x"},
    )
    assert response.status_code == 422


def test_dictionary_intake_empty_word():
    response = client.post(
        "/api/dictionary/suggestions",
        json={"word": "", "category": "Państwo", "starting_letter": "p"},
    )
    assert response.status_code == 422


def test_dictionary_intake_bad_letter():
    response = client.post(
        "/api/dictionary/suggestions",
        json={"word": "Polska", "category": "Państwo", "starting_letter": "ab"},
    )
    assert response.status_code == 422


def test_check_reason_rag_disabled():
    response = client.post(
        "/api/words/check-reason",
        json={"word": "Polska", "category": "Państwo", "starting_letter": "p"},
    )
    assert response.status_code == 503
    assert "wyłączona" in response.json()["detail"].lower()


def test_check_reason_unknown_category(monkeypatch):
    monkeypatch.setenv("PM_RAG_QUEUE_ENABLED", "1")
    response = client.post(
        "/api/words/check-reason",
        json={"word": "X", "category": "Bad", "starting_letter": "x"},
    )
    assert response.status_code == 422


def test_check_reason_empty_word(monkeypatch):
    monkeypatch.setenv("PM_RAG_QUEUE_ENABLED", "1")
    response = client.post(
        "/api/words/check-reason",
        json={"word": "  ", "category": "Państwo", "starting_letter": "p"},
    )
    assert response.status_code == 422


def test_check_reason_missing(monkeypatch):
    monkeypatch.setenv("PM_RAG_QUEUE_ENABLED", "1")
    response = client.post(
        "/api/words/check-reason",
        json={"word": "NigdyNieZgloszone", "category": "Miasto", "starting_letter": "n"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing"
    assert body["ai_reason"] is None
