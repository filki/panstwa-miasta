import pytest
from fastapi.testclient import TestClient

from panstwa_miasta.db import init_db, insert_dictionary_suggestion
from panstwa_miasta.main import app

client = TestClient(app)
WORKER_HEADERS = {"Authorization": "Bearer test-worker-token"}


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.fixture(autouse=True)
def worker_token(monkeypatch):
    monkeypatch.setenv("PM_WORDS_WORKER_TOKEN", "test-worker-token")


@pytest.mark.asyncio
async def test_worker_pending_and_decision():
    suggestion_id = await insert_dictionary_suggestion(
        category="Państwo",
        proposed_norm="wakanda",
        proposed_display="Wakanda",
        target_seed="countries",
        room_id="",
        player_name="",
        letter="w",
        round_no=0,
        ai_explanation="",
    )
    pending = client.get("/api/internal/words/pending", headers=WORKER_HEADERS)
    assert pending.status_code == 200
    body = pending.json()
    assert any(item["id"] == suggestion_id for item in body["items"])

    decided = client.post(
        f"/api/internal/words/{suggestion_id}/decision",
        headers=WORKER_HEADERS,
        json={"status": "accepted", "ai_explanation": "ok", "review_note": "hf"},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "accepted"

    replay = client.post(
        f"/api/internal/words/{suggestion_id}/decision",
        headers=WORKER_HEADERS,
        json={"status": "rejected"},
    )
    assert replay.status_code == 409


def test_worker_auth_required():
    response = client.get("/api/internal/words/pending")
    assert response.status_code == 401


def test_worker_disabled_without_token(monkeypatch):
    monkeypatch.delenv("PM_WORDS_WORKER_TOKEN", raising=False)
    response = client.get("/api/internal/words/pending", headers=WORKER_HEADERS)
    assert response.status_code == 503
