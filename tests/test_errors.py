"""Tests for the global exception handlers in api/errors.py."""

from __future__ import annotations

from unittest.mock import AsyncMock


# ---------------------------------------------------------------------------
# ValueError from mocked agent.register() -> 400 + ErrorResponse shape
# ---------------------------------------------------------------------------

def test_value_error_returns_400_error_response(client, mock_agent):
    """Force a ValueError from a mocked agent.register() -> 400 + ErrorResponse shape."""
    mock_agent.register = AsyncMock(side_effect=ValueError("bad input data"))

    response = client.post("/api/agents/register", json={
        "role": "merchant",
        "display_name": "Error Merchant",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "error@ln.service",
        },
        "service": {
            "service_name": "Error Service",
            "category": "ai_text",
            "price_sats": 50,
            "price_unit": "per_request",
        },
    })

    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert data["message"] == "bad input data"
    assert "details" in data  # field exists (may be None)


# ---------------------------------------------------------------------------
# Generic Exception -> 500 + ErrorResponse shape, no traceback leaked
# ---------------------------------------------------------------------------

def test_generic_exception_returns_500_no_traceback(client, mock_agent):
    """Force a generic Exception -> 500 + ErrorResponse shape, no traceback leaked in body."""
    mock_agent.register = AsyncMock(
        side_effect=RuntimeError("something broke internally")
    )

    response = client.post("/api/agents/register", json={
        "role": "merchant",
        "display_name": "Crash Merchant",
        "lightning": {
            "node_pubkey": "02abcdef1234567890",
            "lightning_address": "crash@ln.service",
        },
        "service": {
            "service_name": "Crash Service",
            "category": "ai_text",
            "price_sats": 50,
            "price_unit": "per_request",
        },
    })

    assert response.status_code == 500
    data = response.json()
    assert data["error_code"] == "INTERNAL_ERROR"
    # Must NOT leak the internal error message or traceback
    assert "something broke internally" not in data["message"]
    assert "Traceback" not in data["message"]
    assert data["message"] == "An unexpected error occurred."
    assert "details" in data
