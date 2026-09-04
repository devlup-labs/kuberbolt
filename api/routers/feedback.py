import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.agent_registry import get_agent_registry
from api.schemas.feedback import CreateFeedbackRequest, CreateFeedbackResponse

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=CreateFeedbackResponse, status_code=201)
async def create_feedback(req: CreateFeedbackRequest):
    registry = await get_agent_registry()
    agent = await registry.get(req.reviewer_pubkey)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{req.reviewer_pubkey}' not registered in session",
        )

    event = await agent.publish_feedback(
        counterparty_pubkey=req.counterparty_pubkey,
        job_id=req.job_id,
        feedback_text=req.feedback_text,
        rating=req.rating,
    )

    return CreateFeedbackResponse(
        event_id=event.id().to_hex(),
        reviewer_pubkey=req.reviewer_pubkey,
        counterparty_pubkey=req.counterparty_pubkey,
        job_id=req.job_id,
        rating=req.rating,
    )