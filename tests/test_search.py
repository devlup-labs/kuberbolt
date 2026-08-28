"""Tests for the GET /api/agents/search endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from tests.conftest import SAMPLE_TAG_SEARCH_RESULTS


# ---------------------------------------------------------------------------
# Successful search
# ---------------------------------------------------------------------------

def test_search_returns_matching_providers(client):
    """GET /api/agents/search?tag=video-analysis -> 200 with matching items."""
    response = client.get("/api/agents/search?tag=video-analysis")

    assert response.status_code == 200
    data = response.json()
    assert data["tag"] == "video-analysis"
    assert data["count"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["author_pubkey"] == "aaa111"
    assert data["items"][1]["event_id"] == "evt2"


# ---------------------------------------------------------------------------
# Tag normalisation
# ---------------------------------------------------------------------------

def test_search_normalises_tag(client):
    """Tags with underscores/spaces/mixed case are normalised before querying."""
    response = client.get("/api/agents/search?tag=Video_Analysis")

    assert response.status_code == 200
    data = response.json()
    # The response echoes back the normalised tag
    assert data["tag"] == "video-analysis"


# ---------------------------------------------------------------------------
# Empty tag -> validation error
# ---------------------------------------------------------------------------

def test_search_empty_tag_returns_400(client):
    """An empty tag string should return a 400 validation error."""
    response = client.get("/api/agents/search?tag=   ")

    assert response.status_code == 400


def test_search_missing_tag_returns_422(client):
    """Missing tag query param entirely -> 422 (FastAPI validation)."""
    response = client.get("/api/agents/search")

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Zero matches -> 200 with empty list
# ---------------------------------------------------------------------------

def test_search_no_matches_returns_empty_list(client):
    """When no providers match the tag -> 200 with items=[], count=0."""
    with patch(
        "api.routers.search.filter_providers_by_tag",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = client.get("/api/agents/search?tag=nonexistent-tag")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["count"] == 0
    assert data["tag"] == "nonexistent-tag"


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------

def test_search_respects_limit_param(client):
    """The limit query param is forwarded to filter_providers_by_tag."""
    with patch(
        "api.routers.search.filter_providers_by_tag",
        new_callable=AsyncMock,
        return_value=SAMPLE_TAG_SEARCH_RESULTS[:1],
    ) as mock_fn:
        response = client.get("/api/agents/search?tag=video-analysis&limit=1")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    # Verify the limit was passed through
    mock_fn.assert_called_once()
    call_args = mock_fn.call_args
    assert call_args.kwargs.get("limit") == 1 or call_args[1].get("limit") == 1
