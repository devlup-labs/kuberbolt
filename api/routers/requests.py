import sys
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException

from api.agent_registry import get_agent_registry
from api.schemas.requests import RequestEndpointRequest, RequestEndpointResponse

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=RequestEndpointResponse)
async def request_endpoint(req: RequestEndpointRequest):
    registry = await get_agent_registry()
    agent = await registry.get(req.agent_pubkey)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{req.agent_pubkey}' not registered in session",
        )

    start_time = time.perf_counter()
    event = await agent.send_handshake(req.provider_pubkey, req.payload)
    replies = await agent.fetch_handshake_replies(timeout_secs=req.timeout_seconds)
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    return RequestEndpointResponse(
        request_id=event.id().to_hex(),
        provider_pubkey=req.provider_pubkey,
        status="success" if replies else "no_reply",
        result=replies[0] if replies else None,
        duration_ms=duration_ms,
    )
