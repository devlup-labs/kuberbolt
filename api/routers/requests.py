import asyncio
import time
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.dependencies import authenticate_agent
from api.schemas.requests import RequestEndpointRequest, RequestEndpointResponse


router = APIRouter(prefix="/api/requests", tags=["requests"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("", response_model=RequestEndpointResponse)
async def request_endpoint(
    req: RequestEndpointRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    agent = await authenticate_agent(req.agent_pubkey, credentials)

    start_time = time.perf_counter()
    event = await agent.send_handshake(req.provider_pubkey, req.payload)
    expected_job_id = req.payload.get("job_id")
    deadline = time.monotonic() + req.timeout_seconds
    replies = []
    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        replies = await agent.fetch_handshake_replies(timeout_secs=min(3, remaining))
        if expected_job_id:
            replies = [reply for reply in replies if reply.get("job_id") == expected_job_id]
        if replies:
            break
        await asyncio.sleep(0.25)
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    return RequestEndpointResponse(
        request_id=event.id().to_hex(),
        provider_pubkey=req.provider_pubkey,
        status="success" if replies else "no_reply",
        result=replies[0] if replies else None,
        duration_ms=duration_ms,
    )
