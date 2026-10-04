import asyncio
from nostr_sdk import Keys, Client, EventBuilder, Kind, Tag, RelayUrl

async def publish_agent(label: str, endpoint: str, relays: list[str]):
    keys = Keys.generate()
    client = Client()
    for r in relays:
        await client.add_relay(RelayUrl.parse(r))
    await client.connect()
    await asyncio.sleep(2)

    tags = [Tag.parse(["d", label]), Tag.parse(["endpoint", endpoint])]
    event = await EventBuilder(Kind(31990), "").tags(tags).finalize_async(keys)
    await client.send_event(event)
    print(f"Published {label}: pubkey={keys.public_key().to_hex()[:16]}... endpoint={endpoint}")
    await client.disconnect()

async def main():
    relays = ["wss://nos.lol", "wss://relay.damus.io"]
    await publish_agent("test-agent-1", "manual-test-machine-1:9001", relays)
    await publish_agent("test-agent-2", "manual-test-machine-2:9002", relays)
    print("\n✅ Test events published! Now watch the brain logs.")

asyncio.run(main())
