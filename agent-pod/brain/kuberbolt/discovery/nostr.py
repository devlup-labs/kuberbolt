"""
Nostr-based peer discovery for the Kuberbolt brain.

Queries Nostr relays for kind-31990 agent listings (NIP-89 style),
extracts their endpoint metadata, and returns them as (peer_a, peer_b) pairs
to hand over to the Go daemon.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger("kuberbolt.brain.discovery")

DEFAULT_RELAYS = [r.strip() for r in
                  os.getenv("KUBERBOLT_RELAYS", "wss://relay.damus.io,wss://nos.lol").split(",")
                  if r.strip()]

# Nostr kind for NIP-89 handler announcements used by Kuberbolt agents
KIND_AGENT_LISTING = 31990
# Fetch window — look back this many seconds for active agents
FETCH_WINDOW_SECS = int(os.getenv("NOSTR_FETCH_WINDOW_SECS", "3600"))


@dataclass
class AgentEndpoint:
    pubkey: str
    endpoint: str   # "host:port" extracted from the listing tags


async def _fetch_listings(relay_url: str, since: int) -> list[dict]:
    """Open a websocket to one relay, send a REQ, collect kind-31990 events."""
    import websockets

    events: list[dict] = []
    sub_id = f"brain-discovery-{int(time.time())}"
    req = json.dumps(["REQ", sub_id, {"kinds": [KIND_AGENT_LISTING], "since": since}])

    try:
        async with websockets.connect(relay_url, open_timeout=5) as ws:
            await ws.send(req)
            async with asyncio.timeout(8):
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg[0] == "EVENT" and msg[1] == sub_id:
                        events.append(msg[2])
                    elif msg[0] == "EOSE":
                        break
    except Exception as exc:
        log.warning(f"Relay {relay_url} error: {exc}")
    return events


def _endpoint_from_event(event: dict) -> str | None:
    """
    Extract the agent's gRPC/HTTP endpoint from NIP-89 tags.
    Looks for a tag of the form: ["endpoint", "host:port"]
    Falls back to ["r", "url"] if present.
    """
    for tag in event.get("tags", []):
        if len(tag) >= 2 and tag[0] == "endpoint":
            return tag[1]
    for tag in event.get("tags", []):
        if len(tag) >= 2 and tag[0] == "r":
            return tag[1]
    return None


async def discover_peers(
    relay_urls: list[str] | None = None,
) -> list[AgentEndpoint]:
    """
    Query all relays concurrently for agent listings published in the last
    FETCH_WINDOW_SECS seconds.  Returns de-duplicated AgentEndpoint list.
    """
    relays = relay_urls or DEFAULT_RELAYS
    since = int(time.time()) - FETCH_WINDOW_SECS

    tasks = [_fetch_listings(url, since) for url in relays]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    peers: list[AgentEndpoint] = []
    for batch in results:
        if isinstance(batch, Exception):
            continue
        for event in batch:
            pubkey = event.get("pubkey", "")
            if pubkey in seen:
                continue
            endpoint = _endpoint_from_event(event)
            if endpoint:
                seen.add(pubkey)
                peers.append(AgentEndpoint(pubkey=pubkey, endpoint=endpoint))

    log.info(f"Discovered {len(peers)} peer(s) across {len(relays)} relay(s)")
    return peers


def peer_pairs(peers: list[AgentEndpoint]) -> list[tuple[AgentEndpoint, AgentEndpoint]]:
    """
    Produce (A, B) pairs from the peer list so each pair can be handed over
    to the daemon as a single HandoverPeers call.
    Consecutive pairs: (0,1), (2,3), ...
    """
    pairs = []
    for i in range(0, len(peers) - 1, 2):
        pairs.append((peers[i], peers[i + 1]))
    return pairs
