from fastapi import APIRouter, Depends

from api.dependencies import get_discovery_agent
from api.schemas.providers import DiscoverProvidersQuery, DiscoverProvidersResponse, ProviderSummary

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=DiscoverProvidersResponse)
async def discover_providers(query: DiscoverProvidersQuery = Depends()):
    agent = await get_discovery_agent()
    items = await agent.discover(
        category=query.category,
        price_max=query.price_max,
        limit=query.limit,
    )
    provider_items = [
        ProviderSummary(
            provider_id=item["provider_id"],
            nostr_pubkey=item["nostr_pubkey"],
            name=item.get("name"),
            picture_url=item.get("picture_url"),
            category=item["category"],
            price_sats=item.get("price_sats"),
            price_unit=item.get("price_unit"),
            service_name=item.get("service_name"),
            service_description=item.get("service_description"),
            listing_event_id=item.get("listing_event_id"),
        )
        for item in items
    ]
    return DiscoverProvidersResponse(items=provider_items, count=len(provider_items))
