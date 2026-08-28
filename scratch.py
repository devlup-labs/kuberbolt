import asyncio
from api.dependencies import get_discovery_agent
from client.kuberbolt.discovery.nostr.filter_providers_by_tag import filter_providers_by_tag

async def main():
    agent = await get_discovery_agent()
    print("Agent connected.")
    try:
        res = await filter_providers_by_tag(agent.client, "bitcoin", limit=1)
        print("Success!", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
