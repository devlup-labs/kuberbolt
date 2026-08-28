import logging
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from nostr_sdk import Keys

from api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_schema_validations():
    # Test LightningCredentials validation
    from api.schemas.agents import LightningCredentials, RegisterAgentRequest, ServiceInfo
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LightningCredentials(node_pubkey="pubkey_123", lnurl=None, lightning_address=None)

    # Test merchant role requires service
    with pytest.raises(ValidationError):
        RegisterAgentRequest(
            role="merchant",
            display_name="Merchant Bob",
            lightning=LightningCredentials(node_pubkey="pubkey_123", lightning_address="bob@ln.service"),
            service=None,
        )

    # Test client role forbids service
    with pytest.raises(ValidationError):
        RegisterAgentRequest(
            role="client",
            display_name="Client Alice",
            lightning=LightningCredentials(node_pubkey="pubkey_123", lightning_address="alice@ln.service"),
            service=ServiceInfo(
                service_name="Test Service",
                category="ai_compute",
                price_sats=100,
                price_unit="per_request",
            ),
        )


def test_register_client():
    request_data = {
        "role": "client",
        "display_name": "Test Client Agent",
        "about": "Testing client registration",
        "picture_url": "https://example.com/pic.png",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "client@example.com",
        },
    }

    response = client.post("/api/agents/register", json=request_data)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["role"] == "client"
    assert "agent_pubkey" in data
    assert "agent_privkey" not in data
    assert data["status"] == "registered"
    assert data["listing_event_id"] is None
    assert "profile_event_id" in data


def test_register_merchant():
    request_data = {
        "role": "merchant",
        "display_name": "Test Merchant Agent",
        "about": "Testing merchant registration",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lnurl": "LNURL123456789",
        },
        "service": {
            "service_name": "AI Text Generation",
            "service_description": "Generates text responses",
            "category": "ai_text",
            "price_sats": 50,
            "price_unit": "per_request",
        },
    }

    response = client.post("/api/agents/register", json=request_data)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["role"] == "merchant"
    assert "agent_pubkey" in data
    assert "agent_privkey" not in data
    assert data["service"]["service_name"] == "AI Text Generation"
    assert data["status"] == "registered"
    assert data["listing_event_id"] is not None


def test_redaction_logging(caplog):
    caplog.set_level(logging.INFO)
    test_key = Keys.generate().secret_key().to_hex()
    dummy_pubkey = Keys.generate().public_key().to_hex()

    response = client.post(
        "/api/requests",
        json={
            "nostr_privkey": test_key,
            "provider_pubkey": dummy_pubkey,
            "payload": {"action": "ping"},
            "timeout_seconds": 1,
        },
    )
    # The actual network request may return success or no_reply depending on relays,
    # but the key MUST NOT appear anywhere in the logs!
    for record in caplog.records:
        assert test_key not in record.message
        if "Incoming Request" in record.message:
            assert "[REDACTED]" in record.message


def test_invalid_nostr_privkey():
    response = client.post(
        "/api/requests",
        json={
            "nostr_privkey": "invalid_privkey_string",
            "provider_pubkey": "0000000000000000000000000000000000000000000000000000000000000000",
            "payload": {"action": "ping"},
        },
    )
    assert response.status_code == 400
    assert response.json()["message"] == "invalid nostr_privkey"


def test_discover_providers():
    response = client.get("/api/providers?category=ai_text&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "count" in data
    assert isinstance(data["items"], list)
    assert data["count"] == len(data["items"])
