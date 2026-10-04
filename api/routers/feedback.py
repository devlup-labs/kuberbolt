
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.dependencies import authenticate_agent
from api.schemas.feedback import CreateFeedbackRequest, CreateFeedbackResponse


router = APIRouter(prefix="/api/feedback", tags=["feedback"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("", response_model=CreateFeedbackResponse, status_code=201)
async def create_feedback(
    req: CreateFeedbackRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    agent = await authenticate_agent(req.reviewer_pubkey, credentials)

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
