import asyncio
import os
import sys
from pathlib import Path

sdk_path = Path(__file__).resolve().parent.parent / "sdk" / "python"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from nostr_sdk_wrapper.agent import KuberboltAgent
from config import get_int_env, get_relays, load_env_file, require_env


async def main():
    load_env_file()
    provider_nsec = require_env("KUBERBOLT_PROVIDER_NSEC")
    identity_path = os.getenv("KUBERBOLT_PROVIDER_IDENTITY_PATH", "examples/provider_identity.json")
    host = os.getenv("KUBERBOLT_PROVIDER_HOST", "127.0.0.1")
    port = get_int_env("KUBERBOLT_PROVIDER_PORT", 54654)

    agent = await KuberboltAgent.from_existing_key(
        privkey_hex=provider_nsec,
        identity_path=identity_path,
        relay_urls=get_relays(),
    )
    try:
        print("provider pubkey:", agent.pubkey_hex)
        print("provider listening for resolve_endpoint handshakes...")
        await agent.serve_endpoint_requests(host=host, port=port)
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
