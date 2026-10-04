"""
Shared fixtures for the Kuberbolt API test suite.

All tests run against a fully-mocked KuberboltAgent so no real relay
connections are ever attempted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import hashlib
import os
from cryptography.fernet import Fernet

os.environ["AGENT_FERNET_KEY"] = Fernet.generate_key().decode()

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Fixed test data
# ---------------------------------------------------------------------------

FAKE_PUBKEY = "a" * 64
SESSION_TOKEN = "test-session-token"
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

    async def _mock_register(*args, **kwargs):
        role = kwargs.get("role", "merchant")
        return {
            "nostr_pubkey": FAKE_PUBKEY,
            "profile_event_id": FAKE_PROFILE_EVENT_ID,
            "listing_event_id": FAKE_LISTING_EVENT_ID if role == "merchant" else None,
        }
    agent.register = AsyncMock(side_effect=_mock_register)

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

    # feedback methods
    mock_feedback_event = MagicMock()
    mock_feedback_event.id.return_value.to_hex.return_value = "feedback_event_hex"
    agent.publish_feedback = AsyncMock(return_value=mock_feedback_event)

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
    from api.agent_registry import FERNET_KEY
    FAKE_ROW = {
        b"token_hash":  hashlib.sha256(SESSION_TOKEN.encode()).digest(),
        b"enc_privkey": Fernet(FERNET_KEY.encode()).encrypt(b"1" * 64),
    }

    async def _mock_hgetall(key):
        if key == f"agent:{FAKE_PUBKEY}":
            return FAKE_ROW
        return {}

    fake_redis = AsyncMock()
    fake_redis.hgetall = AsyncMock(side_effect=_mock_hgetall)
    fake_redis.hset    = AsyncMock()
    fake_redis.expire  = AsyncMock()
    fake_redis.exists  = AsyncMock(return_value=1)
    fake_redis.delete  = AsyncMock()

    from api.agent_registry import _lru
    _lru._cache[FAKE_PUBKEY] = mock_agent

    with (
        patch("api.agent_registry.get_redis", return_value=fake_redis),
        patch("api.routers.agents.KuberboltAgent") as AgentClsAgents,
        patch("sdk.python.nostr_sdk_wrapper.agent.KuberboltAgent") as AgentClsRegistry,
        patch("api.routers.providers.get_discovery_agent", new_callable=AsyncMock) as mock_discovery,
        patch("api.routers.search.get_discovery_agent", new_callable=AsyncMock) as mock_search_discovery,
        patch("api.routers.search.filter_providers_by_tag", new_callable=AsyncMock) as mock_tag_search,
        patch("api.main.get_discovery_agent", new_callable=AsyncMock) as mock_app_discovery,
        patch("api.main.cleanup_discovery_agent", new_callable=AsyncMock) as mock_app_cleanup,
    ):
        AgentClsAgents.create = AsyncMock(return_value=mock_agent)
        AgentClsAgents.from_existing_key = AsyncMock(return_value=mock_agent)
        AgentClsRegistry.from_existing_key = AsyncMock(return_value=mock_agent)

        mock_discovery.return_value = mock_agent
        mock_search_discovery.return_value = mock_agent
        mock_app_discovery.return_value = mock_agent
        mock_app_cleanup.return_value = None

        mock_tag_search.return_value = SAMPLE_TAG_SEARCH_RESULTS

        from api.main import app
        try:
            yield TestClient(app, raise_server_exceptions=False)

        finally:
            _lru._cache.pop(FAKE_PUBKEY, None)
