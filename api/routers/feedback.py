from pathlib import Path

from fastapi import APIRouter
from nostr_sdk import Keys, SecretKey

from api.dependencies import DEFAULT_RELAYS
from api.errors import InvalidPrivkeyError
from api.schemas.feedback import CreateFeedbackRequest, CreateFeedbackResponse


from nostr_sdk_wrapper.agent import KuberboltAgent


router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=CreateFeedbackResponse, status_code=201)
async def create_feedback(req: CreateFeedbackRequest):
    try:
        keys = Keys(SecretKey.parse(req.reviewer_privkey))
    except Exception:
        raise InvalidPrivkeyError("invalid reviewer_privkey")

    agent = None
    try:
        agent = await KuberboltAgent.from_keys(
            keys,
            relay_urls=req.relays or DEFAULT_RELAYS,
        )
        event = await agent.publish_feedback(
            counterparty_pubkey=req.counterparty_pubkey,
            job_id=req.job_id,
            feedback_text=req.feedback_text,
            rating=req.rating,
        )
        reviewer_pubkey = agent.pubkey_hex
    finally:
        if agent is not None:
            await agent.disconnect()

    return CreateFeedbackResponse(
        event_id=event.id().to_hex(),
        reviewer_pubkey=reviewer_pubkey,
        counterparty_pubkey=req.counterparty_pubkey,
        job_id=req.job_id,
        rating=req.rating,
    )