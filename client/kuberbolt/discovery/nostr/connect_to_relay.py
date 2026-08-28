import asyncio
from nostr_sdk import Client, Keys, NostrSigner, RelayUrl
from .generate_key import generate_agent_keys


async def join_to_relays(relay_urls: list[str], keys: Keys) -> Client:
    """
    Takes a list of relay URLs (e.g. 4 public relays) and the agent's keys.
    Initializes a Client, connects to the relays, and returns the Client instance.
    """
    # Initialize the client with the agent's signer keys
    client = Client()
    
    for url in relay_urls:
        await client.add_relay(RelayUrl.parse(url))

    print(f"Connecting to {len(relay_urls)} relays...")
    await client.connect()
    
    # Optional: small sleep to allow WebSocket handshakes to complete
    await asyncio.sleep(3)
    return client

if __name__ == "__main__":
    # Real public Nostr relays for testing
    relay_urls = [
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.primal.net",
        "wss://nostr.wine"
    ]
    
    # Generate agent keys
    keys = generate_agent_keys()
    
    # Run the connection in an asyncio event loop
    asyncio.run(join_to_relays(relay_urls, keys))