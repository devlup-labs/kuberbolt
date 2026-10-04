from tests.conftest import FAKE_PUBKEY, SESSION_TOKEN


def test_create_feedback_publishes_event(client, mock_agent):
    mock_event = mock_agent.publish_feedback.return_value
    mock_event.id.return_value.to_hex.return_value = "feedback_event_hex"

    response = client.post("/api/feedback", json={
        "reviewer_pubkey": FAKE_PUBKEY,
        "counterparty_pubkey": "c" * 64,
        "job_id": "job-123",
        "feedback_text": "Reliable provider",
        "rating": 5,
    }, headers={"Authorization": f"Bearer {SESSION_TOKEN}"})

    assert response.status_code == 201, response.text
    assert response.json() == {
        "event_id": "feedback_event_hex",
        "reviewer_pubkey": FAKE_PUBKEY,
        "counterparty_pubkey": "c" * 64,
        "job_id": "job-123",
        "rating": 5,
        "status": "published",
    }
    mock_agent.publish_feedback.assert_awaited_once_with(
        counterparty_pubkey="c" * 64,
        job_id="job-123",
        feedback_text="Reliable provider",
        rating=5,
    )


def test_create_feedback_rejects_rating_outside_range(client):
    response = client.post("/api/feedback", json={
        "reviewer_pubkey": FAKE_PUBKEY,
        "counterparty_pubkey": "c" * 64,
        "job_id": "job-123",
        "feedback_text": "Invalid rating",
        "rating": 6,
    })

    assert response.status_code == 422


def test_create_feedback_rejects_missing_token(client):
    response = client.post("/api/feedback", json={
        "reviewer_pubkey": FAKE_PUBKEY,
        "counterparty_pubkey": "c" * 64,
        "job_id": "job-123",
        "feedback_text": "Forged feedback",
        "rating": 1,
    })

    assert response.status_code == 401


import pytest
from unittest.mock import AsyncMock
from nostr_sdk import Keys, PublicKey
from sdk.python.nostr_sdk_wrapper.feedback import publish_feedback


@pytest.mark.asyncio
async def test_publish_feedback_builds_event_with_string_job_id():
    mock_client = AsyncMock()
    keys = Keys.generate()
    counterparty = PublicKey.parse("c" * 64)

    event = await publish_feedback(
        client=mock_client,
        reviewer_keys=keys,
        counterparty_pubkey=counterparty,
        job_id="uuid-or-arbitrary-job-id",
        feedback_text="Great service",
        rating=5,
    )

    mock_client.send_event.assert_awaited_once_with(event)
    tags = [t.to_vec() for t in event.tags()]
    assert ["e", "uuid-or-arbitrary-job-id"] in tags
    assert ["p", "c" * 64] in tags