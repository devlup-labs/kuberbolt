"""
Shared fixtures for the Kuberbolt API test suite.

All tests run against a fully-mocked KuberboltAgent so no real relay
connections are ever attempted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.agent_registry import _registry

# ---------------------------------------------------------------------------
# Fixed test data
# ---------------------------------------------------------------------------

FAKE_PUBKEY = "a" * 64
FAKE_PROFILE_EVENT_ID = "c" * 64
FAKE_LISTING_EVENT_ID = "d" * 64

SAMPLE_PROVIDERS = [
    {
        "provider_id": "provider_1",
        "nostr_pubkey": "pub1",
        "name": "AI Text Bot",
        "picture_url": None,
        "category": "ai_text",
        "price_sats": 50,
        "price_unit": "per_request",
        "service_name": "Text Gen",
        "service_description": "Generates text",
        "listing_event_id": "listing1",
    },
    {
        "provider_id": "provider_2",
        "nostr_pubkey": "pub2",
        "name": "Video Bot",
        "picture_url": None,
        "category": "video",
        "price_sats": 200,
        "price_unit": "per_minute",
        "service_name": "Video Analysis",
        "service_description": "Analyses video",
        "listing_event_id": "listing2",
    },
    {
        "provider_id": "provider_3",
        "nostr_pubkey": "pub3",
        "name": "Budget Text",
        "picture_url": None,
        "category": "ai_text",
        "price_sats": 10,
        "price_unit": "flat",
        "service_name": "Cheap Text",
        "service_description": "Basic text",
        "listing_event_id": "listing3",
    },
]

SAMPLE_TAG_SEARCH_RESULTS = [
    {
        "author_pubkey": "aaa111",
        "kind": 1,
        "tags": [["t", "video-analysis"]],
        "content": "I offer video analysis services",
        "event_id": "evt1",
        "created_at": 1700000000,
    },
    {
        "author_pubkey": "bbb222",
        "kind": 31990,
        "tags": [["t", "video-analysis"], ["k", "5202"]],
        "content": "Video AI provider",
        "event_id": "evt2",
        "created_at": 1700000100,
    },
]


# ---------------------------------------------------------------------------
# Mock KuberboltAgent factory
# ---------------------------------------------------------------------------

def _build_mock_agent() -> MagicMock:
    """Return a MagicMock that quacks like KuberboltAgent."""
    agent = MagicMock()
    agent.pubkey_hex = FAKE_PUBKEY

    mock_secret_key = MagicMock()
    mock_secret_key.to_hex.return_value = "1" * 64
    mock_secret_key.to_bech32.return_value = "nsec1test"
    agent.keys.secret_key.return_value = mock_secret_key

    # register() -> dict
    agent.register = AsyncMock(return_value={
        "nostr_pubkey": FAKE_PUBKEY,
        "profile_event_id": FAKE_PROFILE_EVENT_ID,
        "listing_event_id": FAKE_LISTING_EVENT_ID,
    })

    # update_agent() -> dict
    agent.update_agent = AsyncMock(return_value={
        "updated_fields": ["display_name"],
        "profile_event_id": FAKE_PROFILE_EVENT_ID,
        "listing_event_id": FAKE_LISTING_EVENT_ID,
    })

    # publish_profile() -> mock event with .id().to_hex()
    mock_event = MagicMock()
    mock_event.id.return_value.to_hex.return_value = FAKE_PROFILE_EVENT_ID
    agent.publish_profile = AsyncMock(return_value=mock_event)

    # publish_feedback()
    mock_fb_event = MagicMock()
    mock_fb_event.id.return_value.to_hex.return_value = "feedback_event_hex"
    agent.publish_feedback = AsyncMock(return_value=mock_fb_event)

    # disconnect()
    agent.disconnect = AsyncMock()

    # discover() — the discovery agent uses this
    agent.discover = AsyncMock(return_value=SAMPLE_PROVIDERS)

    # handshake methods
    mock_handshake_event = MagicMock()
    mock_handshake_event.id.return_value.to_hex.return_value = "handshake_event_hex"
    agent.send_handshake = AsyncMock(return_value=mock_handshake_event)
    agent.fetch_handshake_replies = AsyncMock(return_value=[{"result": "ok"}])

    return agent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_agent():
    """Provide a fresh mock KuberboltAgent for each test."""
    return _build_mock_agent()


@pytest.fixture()
def client(mock_agent):
    """
    TestClient wired to the real FastAPI app, with KuberboltAgent mocked at
    every import boundary so no network access occurs.
    """
    _registry._agents[FAKE_PUBKEY] = mock_agent

    with (
        patch("api.routers.agents.KuberboltAgent") as AgentClsAgents,
        patch("api.routers.providers.get_discovery_agent", new_callable=AsyncMock) as mock_discovery,
        patch("api.routers.search.get_discovery_agent", new_callable=AsyncMock) as mock_search_discovery,
        patch("api.routers.search.filter_providers_by_tag", new_callable=AsyncMock) as mock_tag_search,
        patch("api.main.get_discovery_agent", new_callable=AsyncMock) as mock_app_discovery,
        patch("api.main.cleanup_discovery_agent", new_callable=AsyncMock) as mock_app_cleanup,
    ):
        AgentClsAgents.create = AsyncMock(return_value=mock_agent)
        AgentClsAgents.from_existing_key = AsyncMock(return_value=mock_agent)

        mock_discovery.return_value = mock_agent
        mock_search_discovery.return_value = mock_agent
        mock_app_discovery.return_value = mock_agent
        mock_app_cleanup.return_value = None

        mock_tag_search.return_value = SAMPLE_TAG_SEARCH_RESULTS

        from api.main import app
        yield TestClient(app, raise_server_exceptions=False)
