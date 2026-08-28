from typing import Any, Literal
from pydantic import BaseModel


class RequestEndpointRequest(BaseModel):
    nostr_privkey: str
    provider_pubkey: str
    payload: dict[str, Any]
    timeout_seconds: int = 30


class RequestEndpointResponse(BaseModel):
    request_id: str
    provider_pubkey: str
    status: Literal["success", "no_reply"]
    result: dict | None = None
    duration_ms: int
