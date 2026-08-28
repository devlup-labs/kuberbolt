from datetime import timedelta

from nostr_sdk import Client, Filter, ReqTarget

async def filter_providers_by_tag(client: Client, tag: str, limit: int = 25) -> list[dict]:
    """
    Filters and fetches providers from the connected relays based on a given tag.
    Returns a structured list of dictionaries for the SDK to process.
    """
    print(f"Searching for providers tagged with #{tag}...")
    
    # Create a filter for the specific hashtag
    # Note: If you want to restrict to a specific kind, you can append .kind(Kind(1)) etc.
    f = Filter().hashtag(tag).limit(limit)
    
    # Fetch the events with an 8-second timeout
    events = await client.fetch_events(ReqTarget.auto([f]), timedelta(seconds=8))
    
    providers = []
    for ev in events:
        providers.append({
            "author_pubkey": ev.author().to_hex(),
            "kind": ev.kind().as_u16(),
            "tags": [t.to_vec() for t in ev.tags()],
            "content": ev.content(),
            "event_id": ev.id().to_hex(),
            "created_at": ev.created_at().as_secs()
        })
        
    print(f"Found {len(providers)} matching provider(s).")
    return providers
