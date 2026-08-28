"""Tests for the /api/requests endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Malformed privkey -> 400 INVALID_PRIVKEY
# ---------------------------------------------------------------------------

def test_malformed_privkey_returns_400(client, mock_agent):
    """malformed nostr_privkey -> 400, error_code='INVALID_PRIVKEY'."""
    # Make SecretKey.parse raise to simulate an invalid key
    with patch("api.routers.requests.SecretKey") as MockSecretKey:
        MockSecretKey.parse.side_effect = Exception("invalid secret key bytes")

        response = client.post("/api/requests", json={
            "nostr_privkey": "not_a_valid_hex_key",
            "provider_pubkey": "0" * 64,
            "payload": {"action": "ping"},
            "timeout_seconds": 5,
        })

    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "INVALID_PRIVKEY"
    assert "invalid" in data["message"].lower()


# ---------------------------------------------------------------------------
# Valid privkey + mocked reply -> success
# ---------------------------------------------------------------------------

def test_valid_privkey_with_reply(client, mock_agent):
    """valid privkey + mocked send_handshake/fetch_handshake_replies with a reply -> success."""
    mock_agent.fetch_handshake_replies = AsyncMock(return_value=[{"result": "ok"}])

    response = client.post("/api/requests", json={
        "nostr_privkey": "a" * 64,
        "provider_pubkey": "0" * 64,
        "payload": {"action": "ping"},
        "timeout_seconds": 5,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"] is not None
    assert data["result"] == {"result": "ok"}


# ---------------------------------------------------------------------------
# Valid privkey + no replies -> no_reply
# ---------------------------------------------------------------------------

def test_valid_privkey_no_reply_timeout(client, mock_agent):
    """valid privkey + no replies within timeout -> status='no_reply', result=None."""
    mock_agent.fetch_handshake_replies = AsyncMock(return_value=[])

    response = client.post("/api/requests", json={
        "nostr_privkey": "a" * 64,
        "provider_pubkey": "0" * 64,
        "payload": {"action": "ping"},
        "timeout_seconds": 1,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_reply"
    assert data["result"] is None
