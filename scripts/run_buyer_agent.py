"""Run the buyer discovery, NIP-44, L402, and service-delivery pipeline."""

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv

load_dotenv()
REPO_ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_POD_PROTO_DIR = REPO_ROOT / "agent-pod" / "proto"


def setting(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def run(prompt: str) -> None:
    started = time.time()
    sdk_server = setting("SDK_SERVER_URL")
    buyer_pubkey = setting("BUYER_NOSTR_PUBKEY")
    session_token = setting("BUYER_SESSION_TOKEN")
    buyer_fp = setting("BUYER_FP_ADDR")

    category = os.getenv("BUYER_SERVICE_CATEGORY", "text-summarization")
    configured_provider_pubkey = os.getenv("BUYER_PROVIDER_PUBKEY", "").strip()
    providers = []
    for attempt in range(3):
        response = requests.get(
            f"{sdk_server}/api/providers",
            params={"category": category},
            timeout=35,
        )
        response.raise_for_status()
        providers = response.json().get("items", [])
        if providers:
            break
        if attempt < 2:
            time.sleep(2)
    if not providers:
        raise RuntimeError(
            "provider discovery returned no providers: "
            f"url={sdk_server}/api/providers category={category!r}"
        )
    provider = providers[0]
    provider_pubkey = configured_provider_pubkey or (
        provider.get("nostr_pubkey") or provider.get("provider_id")
    )
    if not provider_pubkey:
        raise RuntimeError("discovered provider has no Nostr public key")

    job_id = f"job-{uuid4().hex}"
    response = requests.post(
        f"{sdk_server}/api/requests",
        headers={"Authorization": f"Bearer {session_token}"},
        json={
            "agent_pubkey": buyer_pubkey,
            "provider_pubkey": provider_pubkey,
            "payload": {"action": "resolve_endpoint", "job_id": job_id},
            "timeout_seconds": int(os.getenv("HANDSHAKE_TIMEOUT_SECONDS", "30")),
        },
        timeout=40,
    )
    response.raise_for_status()
    request_result = response.json()
    endpoint = request_result.get("result") or {}
    host, port = endpoint.get("host"), endpoint.get("port")
    if not host or not port:
        raise RuntimeError(
            "NIP-44 response did not contain provider host and port: "
            f"status={request_result.get('status')} response={request_result}"
        )

    job_spec = base64.b64encode(json.dumps({"text": prompt}).encode()).decode()
    grpc_args = [
        "grpcurl", "-plaintext",
        "-import-path", str(FINANCIAL_POD_PROTO_DIR),
        "-proto", "agent_service.proto",
        "-d", json.dumps({
            "provider_endpoint": f"{host}:{port}",
            "service_kind": os.getenv("BUYER_SERVICE_KIND", "text-summarization"),
            "job_spec": job_spec,
        }), buyer_fp, "kuberbolt.v1.FinancialPodService/CallService",
    ]
    try:
        result = subprocess.run(
            grpc_args, capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "buyer Financial Pod did not complete the L402 payment within 180 seconds; "
            "verify that the buyer and seller LND nodes are chain-synced and have "
            "an active, funded payment channel"
        ) from error
    if result.returncode != 0:
        raise RuntimeError(f"buyer Financial Pod failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    output_data = payload.get("outputData") or payload.get("output_data")
    if not output_data:
        raise RuntimeError("L402 call returned no service output")
    output = json.loads(base64.b64decode(output_data).decode())
    print(json.dumps({
        "provider_pubkey": provider_pubkey,
        "provider_endpoint": f"{host}:{port}",
        "job_id": job_id,
        "service_output": output,
        "elapsed_seconds": round(time.time() - started, 2),
    }, indent=2))


if __name__ == "__main__":
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else "Summarize the Lightning Network.")
    except (requests.RequestException, RuntimeError, ValueError) as error:
        raise SystemExit(f"pipeline failed: {error}")
