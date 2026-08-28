from pydantic import BaseModel


class DiscoverProvidersQuery(BaseModel):
    category: str
    price_max: int | None = None
    limit: int = 20


class ProviderSummary(BaseModel):
    provider_id: str
    nostr_pubkey: str
    name: str | None = None
    picture_url: str | None = None
    category: str
    price_sats: int | None = None
    price_unit: str | None = None
    service_name: str | None = None
    service_description: str | None = None
    listing_event_id: str | None = None


class DiscoverProvidersResponse(BaseModel):
    items: list[ProviderSummary]
    count: int
