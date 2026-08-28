"""Tests for the /api/providers endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock

from tests.conftest import SAMPLE_PROVIDERS


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------

def test_discover_with_category_filter(client, mock_agent):
    """discover with category filter -> only matching category items returned."""
    # Mock discover to return only items matching the requested category
    ai_text_items = [p for p in SAMPLE_PROVIDERS if p["category"] == "ai_text"]
    mock_agent.discover = AsyncMock(return_value=ai_text_items)

    response = client.get("/api/providers?category=ai_text")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    for item in data["items"]:
        assert item["category"] == "ai_text"


# ---------------------------------------------------------------------------
# Price max filter
# ---------------------------------------------------------------------------

def test_discover_with_price_max(client, mock_agent):
    """discover with price_max -> items above price_max excluded."""
    # Mock returns only items with price_sats <= 50
    cheap_items = [p for p in SAMPLE_PROVIDERS if int(p.get("price_sats") or 0) <= 50]
    mock_agent.discover = AsyncMock(return_value=cheap_items)

    response = client.get("/api/providers?category=ai_text&price_max=50")

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert (item.get("price_sats") or 0) <= 50


# ---------------------------------------------------------------------------
# No matches -> empty list, still 200
# ---------------------------------------------------------------------------

def test_discover_no_matches_returns_200(client, mock_agent):
    """discover with no matches -> items=[], count=0, still 200 (not 404)."""
    mock_agent.discover = AsyncMock(return_value=[])

    response = client.get("/api/providers?category=nonexistent_category")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["count"] == 0
