import asyncio
from asyncio import events
from datetime import timedelta
from nostr_sdk import Client, Filter, RelayUrl
from nostr_sdk import ReqTarget


async def connect_and_filter(relay_urls: list[str], tag: str, limit: int = 10) -> list[dict]:
    """Connects to relays and queries events matching a hashtag."""
    client = Client()

    for url in relay_urls:
        await client.add_relay(RelayUrl.parse(url))

    print(f"Connecting to {len(relay_urls)} relays...")
    await client.connect()
    await asyncio.sleep(2)  # Allow WebSocket handshakes to settle

    print(f"Filtering events tagged with #{tag}...")
    f = Filter().hashtag(tag).limit(limit)
    events = await client.fetch_events(f, timedelta(seconds=8), target=ReqTarget.all())
   
    providers = []
    for ev in events.to_vec():
        providers.append({
            "author_pubkey": ev.author().to_hex(),
            "kind": ev.kind().as_u16(),
            "content": ev.content(),
            "event_id": ev.id().to_hex(),
            "created_at": ev.created_at().as_secs()
        })

    await client.disconnect()
    return providers


if __name__ == "__main__":
    relays = [
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.primal.net"
    ]

    results = asyncio.run(connect_and_filter(relays, tag="bitcoin", limit=5))

    print(f"\nFetched {len(results)} events:\n")
    for i, item in enumerate(results, start=1):
        print(f"[{i}] Author: {item['author_pubkey']}")
        print(f"    Content: {item['content'][:100].strip()}...\n")
