"""
Run this FIRST, on your friend's machine.

Creates (or loads, if already run before) a persistent identity and prints
the pubkey to share with whoever wants to send them an encrypted handshake.
Then listens for incoming handshake messages and decrypts/prints anything
that arrives.

Usage:
    python3 receive_handshake.py
    python3 receive_handshake.py --listen-secs 60   # listen longer
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add the nostr directory to sys.path to find kuberbolt_nostr
_script_dir = Path(__file__).parent.parent
_nostr_dir = _script_dir / "nostr"
if str(_nostr_dir) not in sys.path:
    sys.path.insert(0, str(_nostr_dir))

from kuberbolt_nostr import KuberboltAgent

RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://nostr.wine",
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-secs", type=int, default=30,
                         help="How long to listen for incoming handshakes (default: 30)")
    parser.add_argument("--identity-path", default="my_identity.json",
                         help="Where to store/load this agent's identity (default: my_identity.json)")
    args = parser.parse_args()

    agent = await KuberboltAgent.create(
        identity_path=args.identity_path,
        relay_urls=RELAYS,
    )

    print("=" * 60)
    print("Your pubkey (share this with whoever is sending you a message):")
    print(f"  hex:  {agent.pubkey_hex}")
    print(f"  npub: {agent.npub}")
    print("=" * 60)

    connected = await agent.is_connected()
    if not connected:
        print("\nWARNING: no relays connected. Check your network.")
        await agent.disconnect()
        return

    print(f"\nListening for {args.listen_secs}s for incoming handshake messages...\n")
    replies = await agent.fetch_handshake_replies(timeout_secs=args.listen_secs)

    if not replies:
        print("Got 0 messages. If your friend hasn't sent one yet, run this "
              "again after they do -- relays keep the event around, you "
              "don't need to be listening at the exact moment it's sent.")
    else:
        print(f"Got {len(replies)} message(s):\n")
        for r in replies:
            print(f"  {r}")

    await agent.disconnect()


if __name__ == "__main__":
    asyncio.run(main())