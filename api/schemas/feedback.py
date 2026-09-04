from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    reviewer_pubkey: str
    counterparty_pubkey: str
    job_id: str = Field(min_length=1)
    feedback_text: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    relays: list[str] | None = None


class CreateFeedbackResponse(BaseModel):
    event_id: str
    reviewer_pubkey: str
    counterparty_pubkey: str
    job_id: str
    rating: int
    status: str = "published"