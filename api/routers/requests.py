import sys
import time
from pathlib import Path
from fastapi import APIRouter
from nostr_sdk import Keys, SecretKey

from api.dependencies import DEFAULT_RELAYS
from api.errors import InvalidPrivkeyError
from api.schemas.requests import RequestEndpointRequest, RequestEndpointResponse

sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk" / "python"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

try:
    from nostr_sdk_wrapper.agent import KuberboltAgent
except ImportError:
    from kuberbolt_nostr.agent import KuberboltAgent

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=RequestEndpointResponse)
async def request_endpoint(req: RequestEndpointRequest):
    try:
        keys = Keys(SecretKey.parse(req.nostr_privkey))
    except Exception:
        raise InvalidPrivkeyError("invalid nostr_privkey")

    agent = None
    start_time = time.perf_counter()
    try:
        agent = await KuberboltAgent.from_keys(keys, relay_urls=DEFAULT_RELAYS)
        event = await agent.send_handshake(req.provider_pubkey, req.payload)
        replies = await agent.fetch_handshake_replies(timeout_secs=req.timeout_seconds)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
    finally:
        if agent is not None:
            await agent.disconnect()

    return RequestEndpointResponse(
        request_id=event.id().to_hex(),
        provider_pubkey=req.provider_pubkey,
        status="success" if replies else "no_reply",
        result=replies[0] if replies else None,
        duration_ms=duration_ms,
    )
