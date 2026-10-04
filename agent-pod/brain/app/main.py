"""
Brain service entry point.

Flow:
  1. Connect to the Go daemon over gRPC.
  2. Run a discovery loop every POLL_INTERVAL_SECS:
       a. Query Nostr relays for active agent listings.
       b. Pair them up and call HandoverPeers on the daemon for each pair.
  3. Log the daemon's acknowledgement.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import grpc

# Make the kuberbolt package importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kuberbolt.discovery import discovery_pb2, discovery_pb2_grpc
from kuberbolt.discovery.nostr import discover_peers, peer_pairs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("kuberbolt.brain")

DAEMON_HOST      = os.getenv("DAEMON_HOST", "localhost")
DAEMON_PORT      = os.getenv("DAEMON_PORT", "50051")
POLL_INTERVAL    = int(os.getenv("POLL_INTERVAL_SECS", "60"))
GRPC_MAX_RETRIES = 5


async def handover_peers(stub: discovery_pb2_grpc.NodeManagerStub) -> None:
    """Discover peers from Nostr and hand each pair to the daemon."""
    peers = await discover_peers()
    pairs = peer_pairs(peers)

    if not pairs:
        log.info("No peer pairs to hand over this cycle.")
        return

    for a, b in pairs:
        try:
            resp = stub.HandoverPeers(
                discovery_pb2.PeerHandoverRequest(
                    peer_a_endpoint=a.endpoint,
                    peer_b_endpoint=b.endpoint,
                )
            )
            log.info(
                f"HandoverPeers OK — A={a.endpoint} ({a.pubkey[:8]}…) "
                f"B={b.endpoint} ({b.pubkey[:8]}…) | daemon: {resp.message}"
            )
        except grpc.RpcError as exc:
            log.error(f"HandoverPeers failed: {exc.code()} — {exc.details()}")


async def main() -> None:
    target = f"{DAEMON_HOST}:{DAEMON_PORT}"
    log.info(f"Brain starting — daemon at {target}")

    # Wait for the daemon to be ready (it may still be booting)
    for attempt in range(1, GRPC_MAX_RETRIES + 1):
        try:
            channel = grpc.insecure_channel(target)
            stub = discovery_pb2_grpc.NodeManagerStub(channel)
            # Ping with a known-bad request just to check connectivity
            grpc.channel_ready_future(channel).result(timeout=5)
            break
        except grpc.FutureTimeoutError:
            log.warning(f"Daemon not ready (attempt {attempt}/{GRPC_MAX_RETRIES}), retrying…")
            await asyncio.sleep(2 ** attempt)
    else:
        log.error("Could not connect to daemon after retries — exiting.")
        sys.exit(1)

    log.info("Connected to daemon. Starting discovery loop.")

    while True:
        try:
            await handover_peers(stub)
        except Exception as exc:
            log.error(f"Discovery cycle error: {exc}")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
