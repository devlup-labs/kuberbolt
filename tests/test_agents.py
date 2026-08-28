"""Tests for the /api/agents/register endpoint."""

from __future__ import annotations

import logging

from tests.conftest import FAKE_LISTING_EVENT_ID, FAKE_PUBKEY


# ---------------------------------------------------------------------------
# Happy-path: merchant registration
# ---------------------------------------------------------------------------

def test_register_merchant_with_service(client, mock_agent):
    """Register merchant with valid service -> 201, listing_event_id not None."""
    response = client.post("/api/agents/register", json={
        "role": "merchant",
        "display_name": "Merchant Bob",
        "about": "A test merchant",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "bob@ln.service",
        },
        "service": {
            "service_name": "AI Text Generation",
            "service_description": "Generates text responses",
            "category": "ai_text",
            "price_sats": 50,
            "price_unit": "per_request",
        },
    })

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["agent_pubkey"] == FAKE_PUBKEY
    assert "agent_privkey" not in data
    assert data["listing_event_id"] is not None
    assert data["listing_event_id"] == FAKE_LISTING_EVENT_ID
    assert data["status"] == "registered"


# ---------------------------------------------------------------------------
# Happy-path: client registration
# ---------------------------------------------------------------------------

def test_register_client_no_service(client, mock_agent):
    """Register client (no service field) -> 201, listing_event_id is None."""
    # Configure mock to return None for listing_event_id (client has no listing)
    mock_agent.register.return_value = {
        "nostr_pubkey": FAKE_PUBKEY,
        "profile_event_id": "profile_hex",
        "listing_event_id": None,
    }

    response = client.post("/api/agents/register", json={
        "role": "client",
        "display_name": "Client Alice",
        "about": "A test client",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "alice@ln.service",
        },
    })

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["listing_event_id"] is None
    assert data["role"] == "client"
    assert "agent_privkey" not in data


# ---------------------------------------------------------------------------
# Validation: merchant WITHOUT service -> 400
# ---------------------------------------------------------------------------

def test_register_merchant_without_service_400(client):
    """Register merchant WITHOUT service field -> 400."""
    response = client.post("/api/agents/register", json={
        "role": "merchant",
        "display_name": "Merchant NoService",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "noservice@ln.service",
        },
        # service intentionally omitted
    })

    assert response.status_code == 400 or response.status_code == 422
    # Pydantic validation errors return 422 by default; our model_validator
    # raises ValueError which FastAPI wraps as 422 (RequestValidationError).


# ---------------------------------------------------------------------------
# Validation: client WITH service -> 400
# ---------------------------------------------------------------------------

def test_register_client_with_service_400(client):
    """Register client WITH service field present -> 400."""
    response = client.post("/api/agents/register", json={
        "role": "client",
        "display_name": "Client WithService",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "withservice@ln.service",
        },
        "service": {
            "service_name": "Should Not Be Here",
            "category": "ai_text",
            "price_sats": 50,
            "price_unit": "per_request",
        },
    })

    assert response.status_code == 400 or response.status_code == 422


# ---------------------------------------------------------------------------
# Security: privkey never appears in logs
# ---------------------------------------------------------------------------

def test_privkey_not_leaked_in_logs(client, mock_agent, caplog):
    """Assert response never logs/echoes privkey anywhere but the response body."""
    with caplog.at_level(logging.DEBUG):
        response = client.post("/api/agents/register", json={
            "role": "merchant",
            "display_name": "Log Test Merchant",
            "lightning": {
                "node_pubkey": "02abcdef1234567890",
                "lightning_address": "logtest@ln.service",
            },
            "service": {
                "service_name": "Log Test Service",
                "category": "ai_text",
                "price_sats": 100,
                "price_unit": "per_request",
            },
        })

    assert response.status_code == 201

    data = response.json()
    assert "agent_privkey" not in data

    # But it must NOT appear in any log record
    for record in caplog.records:
        assert "privkey" not in record.message.lower(), (
            f"Privkey leaked in log: {record.message}"
        )
