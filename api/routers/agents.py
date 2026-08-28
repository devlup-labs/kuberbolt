from datetime import datetime, timezone
import os
import sys
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException

from api.dependencies import DEFAULT_RELAYS
from api.schemas.agents import RegisterAgentRequest, RegisterAgentResponse, UpdateAgentRequest, UpdateAgentResponse

sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk" / "python"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from nostr_sdk_wrapper.agent import AgentNotRegisteredError as KuberboltAgentNotRegisteredError, KuberboltAgent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/register", response_model=RegisterAgentResponse, status_code=201)
async def register_agent(req: RegisterAgentRequest):
    with tempfile.TemporaryDirectory() as tmpdir:
        identity_path = os.path.join(tmpdir, "id.json")
        agent = await KuberboltAgent.create(
            identity_path=identity_path,
            relay_urls=req.relays or DEFAULT_RELAYS,
        )
        try:
            lightning_address = (
                req.lightning.lightning_address or req.lightning.lnurl
            )
            result = await agent.register(
                role=req.role,
                display_name=req.display_name,
                about=req.about,
                lightning_address=lightning_address,
                service=req.service.model_dump() if req.service else None,
            )
            if req.picture_url:
                profile_event = await agent.publish_profile(
                    name=req.display_name,
                    about=req.about,
                    picture=req.picture_url,
                    lud16=lightning_address,
                )
                result["profile_event_id"] = profile_event.id().to_hex()
        finally:
            await agent.disconnect()

    return RegisterAgentResponse(
        agent_pubkey=result["nostr_pubkey"],
        role=req.role,
        lightning=req.lightning,
        service=req.service,
        profile_event_id=result["profile_event_id"],
        listing_event_id=result["listing_event_id"],
        status="registered",
        registered_at=datetime.now(timezone.utc),
    )


@router.patch("/update", response_model=UpdateAgentResponse)
async def update_agent(req: UpdateAgentRequest):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            identity_path = os.path.join(tmpdir, "id.json")
            agent = await KuberboltAgent.from_existing_key(
                privkey_hex=req.agent_privkey,
                identity_path=identity_path,
                relay_urls=req.relays or DEFAULT_RELAYS,
            )
            try:
                if agent.pubkey_hex != req.agent_pubkey:
                    raise ValueError(
                        "agent_pubkey does not match the provided private key"
                    )
                result = await agent.update_agent(
                    updates=[u.model_dump() for u in req.updates]
                )
            finally:
                await agent.disconnect()
    except KuberboltAgentNotRegisteredError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return UpdateAgentResponse(
        agent_pubkey=req.agent_pubkey,
        updated_fields=result["updated_fields"],
        profile_event_id=result["profile_event_id"],
        listing_event_id=result["listing_event_id"],
        status="updated",
        updated_at=datetime.now(timezone.utc),
    )
