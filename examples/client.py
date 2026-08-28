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
    client_nsec = require_env("KUBERBOLT_CLIENT_NSEC")
    provider_pubkey = require_env("KUBERBOLT_PROVIDER_PUBKEY")
    identity_path = os.getenv("KUBERBOLT_CLIENT_IDENTITY_PATH", "examples/client_identity.json")
    timeout_seconds = get_int_env("KUBERBOLT_HANDSHAKE_TIMEOUT_SECONDS", 30)

    agent = await KuberboltAgent.from_existing_key(
        privkey_hex=client_nsec,
        identity_path=identity_path,
        relay_urls=get_relays(),
    )
    try:
        print("sending handshake to provider:", provider_pubkey)
        await agent.send_handshake(provider_pubkey, {"action": "resolve_endpoint", "job_id": "test-1"})
        reply = await agent.fetch_handshake_replies(timeout_secs=timeout_seconds)
        print("Got reply:", reply)
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
