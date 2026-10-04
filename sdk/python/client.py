"""
client.py — KuberBolt Discovery Scout (bootstrap phase).

Connects to the Go daemon via an insecure gRPC channel and hands over peer
endpoints supplied by the environment or command line.

No Nostr relay integration, no real peer discovery — that comes later.
"""

import argparse
import os

import grpc

# Generated stubs — produced by protoc from discovery.proto
import discovery_pb2 as pb
import discovery_pb2_grpc as pb_grpc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon-addr", default=os.getenv("DAEMON_ADDR"))
    parser.add_argument("--peer-a", default=os.getenv("PEER_A_ENDPOINT"))
    parser.add_argument("--peer-b", default=os.getenv("PEER_B_ENDPOINT"))
    args = parser.parse_args()
    missing = [name for name, value in {
        "DAEMON_ADDR/--daemon-addr": args.daemon_addr,
        "PEER_A_ENDPOINT/--peer-a": args.peer_a,
        "PEER_B_ENDPOINT/--peer-b": args.peer_b,
    }.items() if not value]
    if missing:
        parser.error("missing configuration: " + ", ".join(missing))

    # Insecure channel — no TLS for this bootstrap phase.
    channel = grpc.insecure_channel(args.daemon_addr)
    stub = pb_grpc.NodeManagerStub(channel)

    request = pb.PeerHandoverRequest(
        peer_a_endpoint=args.peer_a,
        peer_b_endpoint=args.peer_b,
    )

    print(f"[Scout] Sending peers to daemon at {args.daemon_addr}")
    print(f"  Peer A: {args.peer_a}")
    print(f"  Peer B: {args.peer_b}")

    try:
        response: pb.PeerHandoverResponse = stub.HandoverPeers(request)
        print(f"[Scout] Response — success: {response.success}")
        print(f"[Scout] Response — message: {response.message}")
    except grpc.RpcError as e:
        print(f"[Scout] gRPC error: {e.code()} — {e.details()}")


if __name__ == "__main__":
    main()
