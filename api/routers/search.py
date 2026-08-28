"""Router for searching agents/providers by capability tag on the Nostr network."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query

from api.dependencies import get_discovery_agent
from api.normalize import normalize_tag
from api.schemas.search import SearchProviderItem, SearchProvidersResponse

# Ensure the client discovery module is importable
client_path = Path(__file__).resolve().parent.parent.parent / "client"
if str(client_path) not in sys.path:
    sys.path.insert(0, str(client_path))

from kuberbolt.discovery.nostr.filter_providers_by_tag import filter_providers_by_tag

router = APIRouter(prefix="/api/agents", tags=["search"])


@router.get("/search", response_model=SearchProvidersResponse)
async def search_agents_by_tag(
    tag: str = Query(..., description="Capability tag to search for (e.g. 'video-analysis')"),
    limit: int = Query(25, ge=1, le=100, description="Maximum number of results"),
):
    """Search for agents/providers by capability hashtag on the Nostr network."""
    normalised = normalize_tag(tag)
    if not normalised:
        raise ValueError("tag query parameter must not be empty")

    agent = await get_discovery_agent()
    raw_results = await filter_providers_by_tag(agent.client, normalised, limit=limit)

    items = [SearchProviderItem(**provider) for provider in raw_results]
    return SearchProvidersResponse(tag=normalised, count=len(items), items=items)
